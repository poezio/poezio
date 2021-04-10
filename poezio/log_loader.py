import asyncio
import logging
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
from poezio.config import config
from poezio import tabs
from poezio.logger import (
    build_log_message,
    iterate_messages_reverse,
    last_message_in_archive,
    Logger,
)
from poezio.mam import (
    fetch_history,
    NoMAMSupportException,
    MAMQueryException,
    DiscoInfoException,
    make_line,
)
from poezio.common import to_utc
from poezio.ui.types import EndOfArchive, Message, BaseMessage
from poezio.text_buffer import HistoryGap
from slixmpp import JID


log = logging.getLogger(__name__)


def make_line_local(tab: tabs.ChatTab, msg: Dict[str, Any]) -> Message:
    if isinstance(tab, tabs.MucTab):
        jid = JID(tab.jid)
        jid.resource = msg['nickname']
    else:
        jid = JID(tab.jid)
    msg['time'] = msg['time'].astimezone(tz=timezone.utc)
    return make_line(tab, msg['txt'], msg['time'], jid, '')


STATUS = {'mam_only', 'local_only'}


class LogLoader:
    """
    An ephemeral class that loads history in a tab.

    Loading from local logs is blocked until history has been fetched from
    MAM to fill the local archive.
    """
    logger: Logger
    tab: tabs.ChatTab
    mam_only: bool

    def __init__(self, logger: Logger, tab: tabs.ChatTab,
                 mam_only: bool = True):
        self.mam_only = mam_only
        self.logger = logger
        self.tab = tab

    async def tab_open(self):
        """Called on a tab opening or a MUC join"""
        amount = 2 * self.tab.text_win.height
        gap = self.tab._text_buffer.find_last_gap_muc()
        if gap is not None:
            if self.mam_only:
                messages = await self.mam_fill_gap(gap)
            else:
                messages = await self.local_fill_gap(gap)
        else:
            if self.mam_only:
                messages = await self.mam_tab_open(amount)
            else:
                messages = await self.local_tab_open(amount)

        if messages:
            self.tab._text_buffer.add_history_messages(messages)
            self.tab.core.refresh_window()

    async def mam_tab_open(self, nb: int) -> List[BaseMessage]:
        tab = self.tab
        end = datetime.now()
        for message in tab._text_buffer.messages:
            time_ok = to_utc(message.time) < to_utc(end)
            if isinstance(message, Message) and time_ok:
                end = message.time
                break
        end = end - timedelta(microseconds=1)
        try:
            return await fetch_history(tab, end=end, amount=nb)
        except (NoMAMSupportException, MAMQueryException, DiscoInfoException):
            return []
        finally:
            tab.query_status = False

    async def local_tab_open(self, nb: int) -> List[BaseMessage]:
        await self.wait_mam()
        results: List[BaseMessage] = []
        filepath = self.logger.get_file_path(self.tab.jid)
        for msg in iterate_messages_reverse(filepath):
            typ_ = msg.pop('type')
            if typ_ == 'message':
                results.append(make_line_local(self.tab, msg))
            if len(results) >= nb:
                break
        return results[::-1]

    async def mam_fill_gap(self, gap: HistoryGap) -> List[BaseMessage]:
        tab = self.tab

        start = gap.last_timestamp_before_leave
        end = gap.first_timestamp_after_join
        if start:
            start = start + timedelta(seconds=1)
        if end:
            end = end - timedelta(seconds=1)
        try:
            return await fetch_history(tab, start=start, end=end, amount=999)
        except (NoMAMSupportException, MAMQueryException, DiscoInfoException):
            return []
        finally:
            tab.query_status = False

    async def local_fill_gap(self, gap: HistoryGap) -> List[BaseMessage]:
        await self.wait_mam()
        start = gap.last_timestamp_before_leave
        end = gap.first_timestamp_after_join

        results: List[BaseMessage] = []
        filepath = self.logger.get_file_path(self.tab.jid)
        for msg in iterate_messages_reverse(filepath):
            typ_ = msg.pop('type')
            if start and msg['time'] < start:
                break
            if typ_ == 'message' and (not end or msg['time'] < end):
                results.append(make_line_local(self.tab, msg))
        return results[::-1]

    async def scroll_requested(self):
        """When a scroll up is requested in a chat tab.

        Try to load more history if there are no more messages in the buffer.
        """
        tab = self.tab
        tw = tab.text_win

        # If position in the tab is < two screen pages, then fetch MAM, so that
        # wa keep some prefetched margin. A first page should also be
        # prefetched on join if not already available.
        total, pos, height = len(tw.built_lines), tw.pos, tw.height
        rest = (total - pos) // height

        if rest > 1:
            return None

        if self.mam_only:
            messages = await self.mam_scroll_requested(height)
        else:
            messages = await self.local_scroll_requested(height)
        if messages:
            tab._text_buffer.add_history_messages(messages)
            tab.core.refresh_window()

    async def local_scroll_requested(self, nb: int) -> List[BaseMessage]:
        await self.wait_mam()
        tab = self.tab
        last_message_time = None
        if tab._text_buffer.messages:
            last_message_time = to_utc(tab._text_buffer.messages[0].time)
            last_message_time -= timedelta(microseconds=1)

        results: List[BaseMessage] = []
        filepath = self.logger.get_file_path(self.tab.jid)
        for msg in iterate_messages_reverse(filepath):
            typ_ = msg.pop('type')
            if last_message_time is None or msg['time'] < last_message_time:
                if typ_ == 'message':
                    results.append(make_line_local(self.tab, msg))
            if len(results) >= nb:
                break
        return results[::-1]

    async def mam_scroll_requested(self, nb: int) -> List[BaseMessage]:
        tab = self.tab
        try:
            messages = await fetch_history(tab, amount=nb)
            last_message_exists = False
            if tab._text_buffer.messages:
                last_message = tab._text_buffer.messages[0]
                last_message_exists = True
            if (not messages and
                    last_message_exists
                    and not isinstance(last_message, EndOfArchive)):
                time = tab._text_buffer.messages[0].time
                messages = [EndOfArchive('End of archive reached', time=time)]
            return messages
        except NoMAMSupportException:
            return []
        except (MAMQueryException, DiscoInfoException):
            tab.core.information(
                f'An error occured when fetching MAM for {tab.jid}',
                'Error'
            )
            return []
        finally:
            tab.query_status = False

    async def wait_mam(self) -> None:
        if not isinstance(self.tab, tabs.MucTab):
            return
        if self.tab.mam_filler is None:
            return
        await self.tab.mam_filler.done.wait()


class MAMFiller:
    """Class that loads messages from MAM history into the local logs.
    """
    tab: tabs.ChatTab
    logger: Logger
    future: asyncio.Future
    done: asyncio.Event

    def __init__(self, tab: tabs.ChatTab, logger: Logger):
        self.tab = tab
        self.logger = logger
        logger.fd_busy(str(tab.jid))
        self.future = asyncio.ensure_future(self.fetch_routine())
        self.done = asyncio.Event()

    def cancel(self):
        self.future.cancel()
        self.end()

    async def fetch_routine(self) -> None:
        filepath = self.logger.get_file_path(self.tab.jid)
        try:
            last_msg = last_message_in_archive(filepath)
            last_msg_time = None
            if last_msg:
                last_msg_time = last_msg['time'] + timedelta(seconds=1)
            try:
                messages = await fetch_history(
                    self.tab,
                    start=last_msg_time,
                    amount=2000,
                )
            except (DiscoInfoException, NoMAMSupportException, MAMQueryException):
                log.debug('Failed for %s', self.tab.jid, exc_info=True)
                return
            log.debug('Fetched %s:\n%s', len(messages), messages)

            def build_message(msg):
                return build_log_message(
                    msg.nickname,
                    msg.txt,
                    msg.time,
                    prefix='MR',
                )

            logs = ''.join(map(build_message, messages))
            log.debug(logs)

            self.logger.log_raw(self.tab.jid, logs, force=True)
        except Exception as exc:
            log.debug('exception: %s', exc, exc_info=True)
        finally:
            log.debug('finishing fill for %s', self.tab.jid)
            self.end()

    def end(self):
        self.logger.fd_available(str(self.tab.jid))
        self.tab.mam_filler = None
        self.done.set()

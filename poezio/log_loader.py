import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from poezio import tabs
from poezio.logger import iterate_messages_reverse, Logger
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
    return make_line(tab, msg['txt'], msg['time'], jid, '')


STATUS = {'mam_only', 'local_only', 'local_mam_completed'}


class LogLoader:
    """
    An ephemeral class that loads history in a tab
    """
    load_status: str = 'mam_only'
    logger: Logger
    tab: tabs.ChatTab

    def __init__(self, logger: Logger, tab: tabs.ChatTab,
                 load_status: str = 'local_only'):
        if load_status not in STATUS:
            self.load_status = 'mam_only'
        else:
            self.load_status = load_status
        self.logger = logger
        self.tab = tab

    async def tab_open(self):
        """Called on a tab opening or a MUC join"""
        amount = 2 * self.tab.text_win.height
        gap = self.tab._text_buffer.find_last_gap_muc()
        if gap is not None:
            if self.load_status == 'local_only':
                messages = await self.local_fill_gap(gap)
            else:
                messages = await self.mam_fill_gap(gap)
        else:
            if self.load_status == 'mam_only':
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

        if self.load_status == 'mam_only':
            messages = await self.mam_scroll_requested(height)
        else:
            messages = await self.local_scroll_requested(height)
            log.debug('%s %s', messages[0].txt, messages[0].time)
        tab._text_buffer.add_history_messages(messages)
        if messages:
            tab.core.refresh_window()

    async def local_scroll_requested(self, nb: int) -> List[BaseMessage]:
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
            return await self.local_scroll_requested(nb)
        except (MAMQueryException, DiscoInfoException):
            tab.core.information(
                f'An error occured when fetching MAM for {tab.jid}',
                'Error'
            )
            return await self.local_scroll_requested(nb)
        finally:
            tab.query_status = False

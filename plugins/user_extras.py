"""
This plugin enables rich presence events, such as mood, activity, gaming or tune.

.. versionadded:: 0.14
    This plugin was previously provided in the poezio core features.

Command
-------
.. glossary::

    /activity
        **Usage:** ``/activity [<general> [specific] [comment]]``

        Send your current activity to your contacts (use the completion to cycle
        through all the general and specific possible activities).

        Nothing means "stop broadcasting an activity".

    /mood
        **Usage:** ``/mood [<mood> [comment]]``
        Send your current mood to your contacts (use the completion to cycle
        through all the possible moods).

        Nothing means "stop broadcasting a mood".

    /gaming
        **Usage:** ``/gaming [<game name> [server address]]``

        Send your current gaming activity to your contacts.

        Nothing means "stop broadcasting a gaming activity".


Configuration
-------------

.. glossary::

    display_gaming_notifications

        **Default value:** ``true``

        If set to true, notifications about the games your contacts are playing
        will be displayed in the info buffer as 'Gaming' messages.

    display_tune_notifications

        **Default value:** ``true``

        If set to true, notifications about the music your contacts listen to
        will be displayed in the info buffer as 'Tune' messages.

    display_mood_notifications

        **Default value:** ``true``

        If set to true, notifications about the mood of your contacts
        will be displayed in the info buffer as 'Mood' messages.

    display_activity_notifications

        **Default value:** ``true``

        If set to true, notifications about the current activity of your contacts
        will be displayed in the info buffer as 'Activity' messages.

    enable_user_activity

        **Default value:** ``true``

        Set this to ``false`` if you don’t want to receive the activity of your contacts.

    enable_user_gaming

        **Default value:** ``true``

        Set this to ``false`` if you don’t want to receive the gaming activity of your contacts.

    enable_user_mood

        **Default value:** ``true``

        Set this to ``false`` if you don’t want to receive the mood of your contacts.

    enable_user_tune

        **Default value:** ``true``

        If this is set to ``false``, you will no longer be subscribed to tune events,
        and the :term:`display_tune_notifications` option will be ignored.


"""
import asyncio
from functools import reduce
from typing import Dict

from slixmpp import InvalidJID, JID, Message
from poezio.decorators import command_args_parser
from poezio.plugin import BasePlugin
from poezio.roster import roster
from poezio.contact import Contact, Resource
from poezio.core.structs import Completion
from poezio import common
from poezio import tabs


class Plugin(BasePlugin):

    default_config = {
        'user_extras': {
            'display_gaming_notifications': True,
            'display_mood_notifications': True,
            'display_activity_notifications': True,
            'display_tune_notifications': True,
            'enable_user_activity': True,
            'enable_user_gaming': True,
            'enable_user_mood': True,
            'enable_user_tune': True,
        }
    }

    def init(self):
        for plugin in {'xep_0196', 'xep_0108', 'xep_0107', 'xep_0118'}:
            self.core.xmpp.register_plugin(plugin)
        self.api.add_command(
            'activity',
            self.command_activity,
            usage='[<general> [specific] [text]]',
            help='Send your current activity to your contacts '
            '(use the completion). Nothing means '
            '"stop broadcasting an activity".',
            short='Send your activity.',
            completion=self.comp_activity
        )
        self.api.add_command(
            'mood',
            self.command_mood,
            usage='[<mood> [text]]',
            help='Send your current mood to your contacts '
            '(use the completion). Nothing means '
            '"stop broadcasting a mood".',
            short='Send your mood.',
            completion=self.comp_mood,
        )
        self.api.add_command(
            'gaming',
            self.command_gaming,
            usage='[<game name> [server address]]',
            help='Send your current gaming activity to '
            'your contacts. Nothing means "stop '
            'broadcasting a gaming activity".',
            short='Send your gaming activity.',
            completion=None
        )
        handlers = [
            ('user_mood_publish', self.on_mood_event),
            ('user_tune_publish', self.on_tune_event),
            ('user_gaming_publish', self.on_gaming_event),
            ('user_activity_publish', self.on_activity_event),
        ]
        for name, handler in handlers:
            self.core.xmpp.add_event_handler(name, handler)

    def cleanup(self):
        handlers = [
            ('user_mood_publish', self.on_mood_event),
            ('user_tune_publish', self.on_tune_event),
            ('user_gaming_publish', self.on_gaming_event),
            ('user_activity_publish', self.on_activity_event),
        ]
        for name, handler in handlers:
            self.core.xmpp.del_event_handler(name, handler)
        asyncio.create_task(self._stop())

    async def _stop(self):
        await asyncio.gather(
            self.core.xmpp.plugin['xep_0108'].stop(),
            self.core.xmpp.plugin['xep_0107'].stop(),
            self.core.xmpp.plugin['xep_0196'].stop(),
        )


    @command_args_parser.quoted(0, 2)
    async def command_mood(self, args):
        """
        /mood [<mood> [text]]
        """
        if not args:
            return await self.core.xmpp.plugin['xep_0107'].stop()
        mood = args[0]
        if mood not in MOODS:
            return self.core.information(
                '%s is not a correct value for a mood.' % mood, 'Error')
        if len(args) == 2:
            text = args[1]
        else:
            text = None
        await self.core.xmpp.plugin['xep_0107'].publish_mood(
            mood, text
        )

    @command_args_parser.quoted(0, 3)
    async def command_activity(self, args):
        """
        /activity [<general> [specific] [text]]
        """
        length = len(args)
        if not length:
            return await self.core.xmpp.plugin['xep_0108'].stop()

        general = args[0]
        if general not in ACTIVITIES:
            return self.api.information(
                '%s is not a correct value for an activity' % general, 'Error')
        specific = None
        text = None
        if length == 2:
            if args[1] in ACTIVITIES[general]:
                specific = args[1]
            else:
                text = args[1]
        elif length == 3:
            specific = args[1]
            text = args[2]
        if specific and specific not in ACTIVITIES[general]:
            return self.core.information(
                '%s is not a correct value '
                'for an activity' % specific, 'Error')
        await self.core.xmpp.plugin['xep_0108'].publish_activity(
            general, specific, text
        )

    @command_args_parser.quoted(0, 2)
    async def command_gaming(self, args):
        """
        /gaming [<game name> [server address]]
        """
        if not args:
            return await self.core.xmpp.plugin['xep_0196'].stop()

        name = args[0]
        if len(args) > 1:
            address = args[1]
        else:
            address = None
        return await self.core.xmpp.plugin['xep_0196'].publish_gaming(
            name=name, server_address=address
        )

    def comp_activity(self, the_input):
        """Completion for /activity"""
        n = the_input.get_argument_position(quoted=True)
        args = common.shell_split(the_input.text)
        if n == 1:
            return Completion(
                the_input.new_completion,
                sorted(ACTIVITIES.keys()),
                n,
                quotify=True)
        elif n == 2:
            if args[1] in ACTIVITIES:
                l = list(ACTIVITIES[args[1]])
                l.remove('category')
                l.sort()
                return Completion(the_input.new_completion, l, n, quotify=True)

    def comp_mood(self, the_input):
        """Completion for /mood"""
        n = the_input.get_argument_position(quoted=True)
        if n == 1:
            return Completion(
                the_input.new_completion,
                sorted(MOODS.keys()),
                1,
                quotify=True)

    def on_gaming_event(self, message: Message):
        """
        Called when a pep notification for user gaming
        is received
        """
        contact = roster[message['from'].bare]
        if not contact:
            return
        item = message['pubsub_event']['items']['item']
        old_gaming = contact.rich_presence['gaming']
        xml_node = item.xml.find('{urn:xmpp:gaming:0}game')
        # list(xml_node) checks whether there are children or not.
        if xml_node is not None and list(xml_node):
            item = item['gaming']
            # only name and server_address are used for now
            contact.rich_presence['gaming'] = {
                'character_name': item['character_name'],
                'character_profile': item['character_profile'],
                'name': item['name'],
                'level': item['level'],
                'uri': item['uri'],
                'server_name': item['server_name'],
                'server_address': item['server_address'],
            }
        else:
            contact.rich_presence['gaming'] = {}

        if old_gaming != contact.rich_presence['gaming'] and self.config.get(
                'display_gaming_notifications'):
            if contact.rich_presence['gaming']:
                self.core.information(
                    '%s is playing %s' % (contact.bare_jid,
                                          common.format_gaming_string(
                                              contact.rich_presence['gaming'])), 'Gaming')
            else:
                self.core.information(contact.bare_jid + ' stopped playing.',
                                      'Gaming')

    def on_mood_event(self, message: Message):
        """
        Called when a pep notification for a user mood
        is received.
        """
        contact = roster[message['from'].bare]
        if not contact:
            return
        item = message['pubsub_event']['items']['item']
        old_mood = contact.rich_presence.get('mood')
        plugin = item.get_plugin('mood', check=True)
        if plugin:
            mood = item['mood']['value']
        else:
            mood = ''
        if mood:
            mood = MOODS.get(mood, mood)
            text = item['mood']['text']
            if text:
                mood = '%s (%s)' % (mood, text)
            contact.rich_presence['mood'] = mood
        else:
            contact.rich_presence['mood'] = ''

        if old_mood != contact.rich_presence['mood'] and self.config.get(
                'display_mood_notifications'):
            if contact.rich_presence['mood']:
                self.core.information(
                    'Mood from ' + contact.bare_jid + ': ' + contact.rich_presence['mood'],
                    'Mood')
            else:
                self.core.information(
                    contact.bare_jid + ' stopped having their mood.', 'Mood')

    def on_activity_event(self, message: Message):
        """
        Called when a pep notification for a user activity
        is received.
        """
        contact = roster[message['from'].bare]
        if not contact:
            return
        item = message['pubsub_event']['items']['item']
        old_activity = contact.rich_presence['activity']
        xml_node = item.xml.find('{http://jabber.org/protocol/activity}activity')
        # list(xml_node) checks whether there are children or not.
        if xml_node is not None and list(xml_node):
            try:
                activity = item['activity']['value']
            except ValueError:
                return
            if activity[0]:
                general = ACTIVITIES.get(activity[0])
                if general is None:
                    return
                s = general['category']
                if activity[1]:
                    s = s + '/' + general.get(activity[1], 'other')
                text = item['activity']['text']
                if text:
                    s = '%s (%s)' % (s, text)
                contact.rich_presence['activity'] = s
            else:
                contact.rich_presence['activity'] = ''
        else:
            contact.rich_presence['activity'] = ''

        if old_activity != contact.rich_presence['activity'] and self.config.get(
                'display_activity_notifications'):
            if contact.rich_presence['activity']:
                self.core.information(
                    'Activity from ' + contact.bare_jid + ': ' +
                    contact.rich_presence['activity'], 'Activity')
            else:
                self.core.information(
                    contact.bare_jid + ' stopped doing their activity.',
                    'Activity')

    def on_tune_event(self, message: Message):
        """
        Called when a pep notification for a user tune
        is received
        """
        contact = roster[message['from'].bare]
        if not contact:
            return
        roster.modified()
        item = message['pubsub_event']['items']['item']
        old_tune = contact.rich_presence['tune']
        xml_node = item.xml.find('{http://jabber.org/protocol/tune}tune')
        # list(xml_node) checks whether there are children or not.
        if xml_node is not None and list(xml_node):
            item = item['tune']
            contact.rich_presence['tune'] = {
                'artist': item['artist'],
                'length': item['length'],
                'rating': item['rating'],
                'source': item['source'],
                'title': item['title'],
                'track': item['track'],
                'uri': item['uri']
            }
        else:
            contact.rich_presence['tune'] = {}

        if old_tune != contact.rich_presence['tune'] and self.config.get(
                'display_tune_notifications'):
            if contact.rich_presence['tune']:
                self.core.information(
                    'Tune from ' + message['from'].bare + ': ' +
                    common.format_tune_string(contact.rich_presence['tune']), 'Tune')
            else:
                self.core.information(
                    contact.bare_jid + ' stopped listening to music.', 'Tune')


# Collection of mappings for PEP moods/activities
# extracted directly from the XEP

MOODS: Dict[str, str] = {
    'afraid': 'Afraid',
    'amazed': 'Amazed',
    'angry': 'Angry',
    'amorous': 'Amorous',
    'annoyed': 'Annoyed',
    'anxious': 'Anxious',
    'aroused': 'Aroused',
    'ashamed': 'Ashamed',
    'bored': 'Bored',
    'brave': 'Brave',
    'calm': 'Calm',
    'cautious': 'Cautious',
    'cold': 'Cold',
    'confident': 'Confident',
    'confused': 'Confused',
    'contemplative': 'Contemplative',
    'contented': 'Contented',
    'cranky': 'Cranky',
    'crazy': 'Crazy',
    'creative': 'Creative',
    'curious': 'Curious',
    'dejected': 'Dejected',
    'depressed': 'Depressed',
    'disappointed': 'Disappointed',
    'disgusted': 'Disgusted',
    'dismayed': 'Dismayed',
    'distracted': 'Distracted',
    'embarrassed': 'Embarrassed',
    'envious': 'Envious',
    'excited': 'Excited',
    'flirtatious': 'Flirtatious',
    'frustrated': 'Frustrated',
    'grumpy': 'Grumpy',
    'guilty': 'Guilty',
    'happy': 'Happy',
    'hopeful': 'Hopeful',
    'hot': 'Hot',
    'humbled': 'Humbled',
    'humiliated': 'Humiliated',
    'hungry': 'Hungry',
    'hurt': 'Hurt',
    'impressed': 'Impressed',
    'in_awe': 'In awe',
    'in_love': 'In love',
    'indignant': 'Indignant',
    'interested': 'Interested',
    'intoxicated': 'Intoxicated',
    'invincible': 'Invincible',
    'jealous': 'Jealous',
    'lonely': 'Lonely',
    'lucky': 'Lucky',
    'mean': 'Mean',
    'moody': 'Moody',
    'nervous': 'Nervous',
    'neutral': 'Neutral',
    'offended': 'Offended',
    'outraged': 'Outraged',
    'playful': 'Playful',
    'proud': 'Proud',
    'relaxed': 'Relaxed',
    'relieved': 'Relieved',
    'remorseful': 'Remorseful',
    'restless': 'Restless',
    'sad': 'Sad',
    'sarcastic': 'Sarcastic',
    'serious': 'Serious',
    'shocked': 'Shocked',
    'shy': 'Shy',
    'sick': 'Sick',
    'sleepy': 'Sleepy',
    'spontaneous': 'Spontaneous',
    'stressed': 'Stressed',
    'strong': 'Strong',
    'surprised': 'Surprised',
    'thankful': 'Thankful',
    'thirsty': 'Thirsty',
    'tired': 'Tired',
    'undefined': 'Undefined',
    'weak': 'Weak',
    'worried': 'Worried'
}

ACTIVITIES: Dict[str, Dict[str, str]] = {
    'doing_chores': {
        'category': 'Doing_chores',
        'buying_groceries': 'Buying groceries',
        'cleaning': 'Cleaning',
        'cooking': 'Cooking',
        'doing_maintenance': 'Doing maintenance',
        'doing_the_dishes': 'Doing the dishes',
        'doing_the_laundry': 'Doing the laundry',
        'gardening': 'Gardening',
        'running_an_errand': 'Running an errand',
        'walking_the_dog': 'Walking the dog',
        'other': 'Other',
    },
    'drinking': {
        'category': 'Drinking',
        'having_a_beer': 'Having a beer',
        'having_coffee': 'Having coffee',
        'having_tea': 'Having tea',
        'other': 'Other',
    },
    'eating': {
        'category': 'Eating',
        'having_breakfast': 'Having breakfast',
        'having_a_snack': 'Having a snack',
        'having_dinner': 'Having dinner',
        'having_lunch': 'Having lunch',
        'other': 'Other',
    },
    'exercising': {
        'category': 'Exercising',
        'cycling': 'Cycling',
        'dancing': 'Dancing',
        'hiking': 'Hiking',
        'jogging': 'Jogging',
        'playing_sports': 'Playing sports',
        'running': 'Running',
        'skiing': 'Skiing',
        'swimming': 'Swimming',
        'working_out': 'Working out',
        'other': 'Other',
    },
    'grooming': {
        'category': 'Grooming',
        'at_the_spa': 'At the spa',
        'brushing_teeth': 'Brushing teeth',
        'getting_a_haircut': 'Getting a haircut',
        'shaving': 'Shaving',
        'taking_a_bath': 'Taking a bath',
        'taking_a_shower': 'Taking a shower',
        'other': 'Other',
    },
    'having_appointment': {
        'category': 'Having appointment',
        'other': 'Other',
    },
    'inactive': {
        'category': 'Inactive',
        'day_off': 'Day_off',
        'hanging_out': 'Hanging out',
        'hiding': 'Hiding',
        'on_vacation': 'On vacation',
        'praying': 'Praying',
        'scheduled_holiday': 'Scheduled holiday',
        'sleeping': 'Sleeping',
        'thinking': 'Thinking',
        'other': 'Other',
    },
    'relaxing': {
        'category': 'Relaxing',
        'fishing': 'Fishing',
        'gaming': 'Gaming',
        'going_out': 'Going out',
        'partying': 'Partying',
        'reading': 'Reading',
        'rehearsing': 'Rehearsing',
        'shopping': 'Shopping',
        'smoking': 'Smoking',
        'socializing': 'Socializing',
        'sunbathing': 'Sunbathing',
        'watching_a_movie': 'Watching a movie',
        'watching_tv': 'Watching tv',
        'other': 'Other',
    },
    'talking': {
        'category': 'Talking',
        'in_real_life': 'In real life',
        'on_the_phone': 'On the phone',
        'on_video_phone': 'On video phone',
        'other': 'Other',
    },
    'traveling': {
        'category': 'Traveling',
        'commuting': 'Commuting',
        'driving': 'Driving',
        'in_a_car': 'In a car',
        'on_a_bus': 'On a bus',
        'on_a_plane': 'On a plane',
        'on_a_train': 'On a train',
        'on_a_trip': 'On a trip',
        'walking': 'Walking',
        'cycling': 'Cycling',
        'other': 'Other',
    },
    'undefined': {
        'category': 'Undefined',
        'other': 'Other',
    },
    'working': {
        'category': 'Working',
        'coding': 'Coding',
        'in_a_meeting': 'In a meeting',
        'writing': 'Writing',
        'studying': 'Studying',
        'other': 'Other',
    }
}

"""
This plugin lets you set the CSI_ state manually, when the autoaway plugin
is not sufficient for your usage.

Commands
--------

.. glossary::

    /csi_active
        **Usage:** ``/csi_active``

        Set CSI state to ``active``.

    /csi_inactive
        **Usage:** ``/csi_inactive``

        Set CSI state to ``inactive``.

.. _CSI: https://xmpp.org/extensions/xep-0352.html
"""

from poezio.plugin import BasePlugin

class Plugin(BasePlugin):
    def init(self):
        self.api.add_command('csi_active', self.command_active,
                             help='Set the client state indication to “active”',
                             short='Manual set active')
        self.api.add_command('csi_inactive', self.command_inactive,
                             help='Set the client state indication to “inactive”',
                             short='Manual set inactive')

    def command_active(self, args):
        if not self.core.xmpp.plugin['xep_0352'].enabled:
            self.api.information('CSI is not enabled in this server', 'Warning')
        else:
            self.core.xmpp.plugin['xep_0352'].send_active()

    def command_inactive(self, args):
        if not self.core.xmpp.plugin['xep_0352'].enabled:
            self.api.information('CSI is not enabled in this server', 'Warning')
        else:
            self.core.xmpp.plugin['xep_0352'].send_inactive()

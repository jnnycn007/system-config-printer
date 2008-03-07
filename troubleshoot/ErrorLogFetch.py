#!/usr/bin/env python

## Printing troubleshooter

## Copyright (C) 2008 Red Hat, Inc.
## Copyright (C) 2008 Tim Waugh <twaugh@redhat.com>

## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.

## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.

## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import cups
import os
import tempfile
from base import *
from base import _
class ErrorLogFetch(Question):
    def __init__ (self, troubleshooter):
        Question.__init__ (self, troubleshooter, "Error log fetch")
        page = self.initial_vbox (_("Debugging"),
                                  _("I would like to disable debugging output "
                                    "from the CUPS scheduler.  This may "
                                    "cause the scheduler to restart.  Click "
                                    "the button below to disable debugging."))
        button = gtk.Button (_("Disable Debugging"))
        buttonbox = gtk.HButtonBox ()
        buttonbox.set_border_width (0)
        buttonbox.set_layout (gtk.BUTTONBOX_START)
        buttonbox.pack_start (button, False, False, 0)
        self.button = button
        page.pack_start (buttonbox, False, False, 0)
        self.label = gtk.Label ()
        self.label.set_alignment (0, 0)
        self.label.set_line_wrap (True)
        page.pack_start (self.label, False, False, 0)
        troubleshooter.new_page (page, self)
        self.persistent_answers = {}

    def display (self):
        answers = self.troubleshooter.answers
        self.answers = {}
        try:
            checkpoint = answers['error_log_checkpoint']
        except KeyError:
            checkpoint = None

        if self.persistent_answers.has_key ('error_log'):
            checkpoint = None

        if checkpoint != None:
            # Fail if auth required.
            cups.setPasswordCB (lambda x: '')
            cups.setServer ('')
            try:
                c = cups.Connection ()
            except RuntimeError:
                return {}

            (tmpfd, tmpfname) = tempfile.mkstemp ()
            os.close (tmpfd)
            try:
                c.getFile ('/admin/log/error_log', tmpfname)
            except cups.IPPError:
                os.remove (tmpfname)
                return {}

            f = file (tmpfname)
            f.seek (checkpoint)
            lines = f.readlines ()
            os.remove (tmpfname)
            self.answers = { 'error_log': map (lambda x: x.strip (), lines) }

        if answers.has_key ('error_log_debug_logging_set'):
            return True

        return False

    def connect_signals (self, handler):
        self.button_sigid = self.button.connect ('clicked', self.button_clicked)

    def disconnect_signals (self):
        self.button.disconnect (self.button_sigid)

    def collect_answer (self):
        answers = self.persistent_answers.copy ()
        answers.update (self.answers)
        return answers

    def button_clicked (self, button):
        auth = self.troubleshooter.answers['_authentication_dialog']
        for user in ['', 'root']:
            cups.setUser (user)
            if user == '':
                # First try with the current user and no password.
                cups.setPasswordCB (lambda x: '')
            else:
                # Then try with root and an authentication dialog.
                cups.setPasswordCB (auth.callback)

            try:
                c = cups.Connection ()
            except RuntimeError:
                return

            try:
                auth.suppress_dialog ()
                settings = c.adminGetServerSettings ()
            except cups.IPPError:
                settings = {}

            if len (settings.keys ()) == 0:
                if user != '':
                    return

        try:
            prev = int (settings[cups.CUPS_SERVER_DEBUG_LOGGING])
        except KeyError:
            prev = 0

        if prev != 0:
            settings[cups.CUPS_SERVER_DEBUG_LOGGING] = '0'
            success = False
            try:
                auth.suppress_dialog ()
                c.adminSetServerSettings (settings)
                success = True
            except cups.IPPError:
                pass

            if success:
                self.persistent_answers['error_log_debug_logging_unset'] = True
                self.label.set_text (_("Debug logging disabled."))
        else:
            self.label.set_text (_("Debug logging was already disabled."))
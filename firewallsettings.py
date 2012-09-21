#!/usr/bin/python

## system-config-printer

## Copyright (C) 2006, 2007, 2008, 2009, 2010, 2011 Red Hat, Inc.
## Authors:
##  Tim Waugh <twaugh@redhat.com>

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
## Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

# config is generated from config.py.in by configure
import config

import dbus
import json
from debug import *

IPP_CLIENT_SERVICE   = "ipp-client"
IPP_CLIENT_PORT      = "631"
IPP_CLIENT_PROTOCOL  = "udp"
IPP_SERVER_SERVICE   = "ipp"
IPP_SERVER_PORT      = "631"
IPP_SERVER_PROTOCOL  = "tcp"
MDNS_SERVICE         = "mdns"
MDNS_PORT            = "5353"
MDNS_PROTOCOL        = "udp"
SAMBA_CLIENT_SERVICE = "samba-client"

class FirewallD:
    DBUS_INTERFACE = "org.fedoraproject.FirewallD1"
    DBUS_INTERFACE_ZONE = DBUS_INTERFACE+".zone"
    DBUS_INTERFACE_CONFIG = DBUS_INTERFACE+".config"
    DBUS_PATH = "/org/fedoraproject/FirewallD1"
    DBUS_PATH_CONFIG = DBUS_PATH+"/config"
    services_idx = 5
    ports_idx = 6
    def __init__ (self):
        try:
            bus = dbus.SystemBus ()
            obj = bus.get_object (self.DBUS_INTERFACE, self.DBUS_PATH)
            self._fw = dbus.Interface(obj, self.DBUS_INTERFACE)
            self._fw_zone = dbus.Interface(obj, self.DBUS_INTERFACE_ZONE)
            self._fw_properties = dbus.Interface(obj,
                            dbus_interface='org.freedesktop.DBus.Properties')
            obj_config = bus.get_object (self.DBUS_INTERFACE,
                                         self.DBUS_PATH_CONFIG)
            self._fw_config = dbus.Interface (obj_config,
                                              self.DBUS_INTERFACE_CONFIG)
            zone_name = self._get_active_zone ()
            if zone_name:
                zone_path = self._fw_config.getZoneByName (zone_name)
                self._zone = bus.get_object (self.DBUS_INTERFACE, zone_path)
            else:
                self._zone = None
            debugprint ("Using /org/fedoraproject/FirewallD1")
        except (ImportError, dbus.DBusException):
            self._fw = None
            self._fw_zone = None
            self._fw_properties = None
            self._fw_config = None
            self._zone = None

    def running (self):
        return self._fw_properties and \
               str(self._fw_properties.Get(self.DBUS_INTERFACE, "state")) \
               == "RUNNING"

    def _get_active_zone (self):
        try:
            zones = map (str, self._fw_zone.getActiveZones())
            # remove immutable zones
            zones = [z for z in zones if not self._fw_zone.isImmutable(z)]
        except dbus.DBusException:
            debugprint ("FirewallD getting active zones failed")
            zones = None

        if not zones:
            debugprint ("FirewallD: no changeable zone")
            return None
        elif len (zones) == 1:
            # most probable case
            return zones[0]
        else:
            # Do we need to handle the 'more active zones' case ?
            # It's quite unlikely case because that would mean that more
            # network connections are up and running and they are
            # in different network zones at the same time.
            debugprint ("FirewallD returned more zones, taking first one")
            return zones[0]

    def _get_fw_data (self, reply_handler=None, error_handler=None):
        try:
            repr_data = map (str, self._fw_data[self.services_idx])
            debugprint ("%s in _get_fw_data: _fw_data is %s" %
                        (self, repr(repr_data)))
            if self._fw_data:
                debugprint ("Using cached firewall data")
                if reply_handler:
                    reply_handler (self._fw_data)
        except AttributeError:
            try:
                self._fw_data = self._zone.getSettings ()
                debugprint ("Firewall data obtained")
                if reply_handler:
                    reply_handler (self._fw_data) 
            except (dbus.DBusException, AttributeError, ValueError), e:
                self._fw_data = None
                debugprint ("Exception examining firewall")
                if error_handler:
                    error_handler (e)

        return self._fw_data

    def read (self, reply_handler=None, error_handler=None):
        if reply_handler:
            self._get_fw_data (reply_handler,
                               error_handler)
        else:
            self._get_fw_data ()

    def write (self):
        if self._zone:
            self._zone.update (self._fw_data)
        self._fw.reload ()

    def add_service (self, service):
        if not self._get_fw_data ():
            return

        #self._fw_data.addService (service)
        if service not in self._fw_data[self.services_idx]:
            self._fw_data[self.services_idx].append(service)

    def check_ipp_client_allowed (self):
        if not self._get_fw_data ():
            return True

        return (IPP_CLIENT_SERVICE in self._fw_data[self.services_idx] or
               [IPP_CLIENT_PORT, IPP_CLIENT_PROTOCOL] in self._fw_data[self.ports_idx])

    def check_ipp_server_allowed (self):
        if not self._get_fw_data ():
            return True

        return (IPP_SERVER_SERVICE in self._fw_data[self.services_idx] or
               [IPP_SERVER_PORT, IPP_SERVER_PROTOCOL] in self._fw_data[self.ports_idx])

    def check_samba_client_allowed (self):
        if not self._get_fw_data ():
            return True

        return (IPP_CLIENT_SERVICE in self._fw_data[self.services_idx])

    def check_mdns_allowed (self):
        if not self._get_fw_data ():
            return True

        return (MDNS_SERVICE in self._fw_data[self.services_idx] or
               [MDNS_PORT, MDNS_PROTOCOL] in self._fw_data[self.ports_idx])



class SystemConfigFirewall:
    DBUS_INTERFACE = "org.fedoraproject.Config.Firewall"
    DBUS_PATH = "/org/fedoraproject/Config/Firewall"

    def __init__(self):
        try:
            bus = dbus.SystemBus ()
            obj = bus.get_object (self.DBUS_INTERFACE, self.DBUS_PATH)
            self._fw = dbus.Interface (obj, self.DBUS_INTERFACE)
            debugprint ("Using system-config-firewall")
        except (dbus.DBusException), e:
            debugprint ("No firewall ")
            self._fw = None
            self._fw_data = (None, None)

    def _get_fw_data (self, reply_handler=None, error_handler=None):
        try:
            debugprint ("%s in _get_fw_data: _fw_data is %s" %
                        (self, repr(self._fw_data)))
            if self._fw_data:
                debugprint ("Using cached firewall data")
                if reply_handler == None:
                    return self._fw_data

                self._client_reply_handler (self._fw_data)
        except AttributeError:
            try:
                if reply_handler:
                    self._fw.read (reply_handler=reply_handler,
                                   error_handler=error_handler)
                    return

                p = self._fw.read ()
                self._fw_data = json.loads (p.encode ('utf-8'))
            except (dbus.DBusException, AttributeError, ValueError), e:
                self._fw_data = (None, None)
                if error_handler:
                    debugprint ("Exception examining firewall")
                    self._client_error_handler (e)

        return self._fw_data

    def read (self, reply_handler=None, error_handler=None):
        if reply_handler:
            self._client_reply_handler = reply_handler
            self._client_error_handler = error_handler
            self._get_fw_data (reply_handler=self.reply_handler,
                               error_handler=self.error_handler)
        else:
            self._get_fw_data ()

    def reply_handler (self, result):
        try:
            self._fw_data = json.loads (result.encode ('utf-8'))
        except ValueError, e:
            self.error_handler (e)
            return

        debugprint ("Firewall data obtained")
        self._client_reply_handler (self._fw_data)

    def error_handler (self, exc):
        debugprint ("Exception fetching firewall data")
        self._client_error_handler (exc)

    def write (self):
        try:
            self._fw.write (json.dumps (self._fw_data[0]))
        except:
            pass

    def _check_any_allowed (self, search):
        (args, filename) = self._get_fw_data ()
        if filename == None: return True
        isect = set (search).intersection (set (args))
        return len (isect) != 0


    def add_service (self, service):
        try:
            (args, filename) = self._fw_data
        except AttributeError:
            (args, filename) = self._get_fw_data ()
        if filename == None: return

        args.append ("--service=" + service)
        self._fw_data = (args, filename)

    def check_ipp_client_allowed (self):
        return self._check_any_allowed (set(["--port=%s:%s" %
                                        (IPP_CLIENT_PORT, IPP_CLIENT_PROTOCOL),
                                             "--service=" + IPP_CLIENT_SERVICE]))

    def check_ipp_server_allowed (self):
        return self._check_any_allowed (set(["--port=%s:%s" %
                                        (IPP_SERVER_PORT, IPP_SERVER_PROTOCOL),
                                             "--service=" + IPP_SERVER_SERVICE]))

    def check_samba_client_allowed (self):
        return self._check_any_allowed (set(["--service=" + SAMBA_CLIENT_SERVICE]))

    def check_mdns_allowed (self):
        return self._check_any_allowed (set(["--port=%s:%s" %
                                                    (MDNS_PORT, MDNS_PROTOCOL),
                                             "--service=" + MDNS_SERVICE]))

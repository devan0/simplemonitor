# coding=utf-8
"""A (fairly) simple host/service monitor."""


import os
import sys
import time

from envconfig import EnvironmentAwareConfigParser

from optparse import OptionParser, SUPPRESS_HELP

from socket import gethostname

import Monitors.monitor
import Monitors.network
import Monitors.service
import Monitors.host
import Monitors.file
import Monitors.compound

from simplemonitor import SimpleMonitor

import Loggers.file
import Loggers.db
import Loggers.network

import Alerters.mail
import Alerters.ses
import Alerters.bulksms
import Alerters.fortysixelks
import Alerters.syslogger
import Alerters.execute
import Alerters.slack
import Alerters.pushover
import Alerters.nma
import Alerters.pushbullet


VERSION = "1.7"


def get_config_dict(config, monitor):
    options = config.items(monitor)
    ret = {}
    for (key, value) in options:
        ret[key] = value
    return ret


def load_monitors(m, filename, quiet):
    """Load all the monitors from the config file and return a populated SimpleMonitor."""
    config = EnvironmentAwareConfigParser()
    config.read(filename)
    monitors = config.sections()
    if "defaults" in monitors:
        default_config = get_config_dict(config, "defaults")
        monitors.remove("defaults")
    else:
        default_config = {}

    myhostname = gethostname().lower()

    for monitor in monitors:
        if config.has_option(monitor, "runon"):
            if myhostname != config.get(monitor, "runon").lower():
                sys.stderr.write("Ignoring monitor %s because it's only for host %s\n" % (monitor, config.get(monitor, "runon")))
                continue
        type = config.get(monitor, "type")
        new_monitor = None
        config_options = default_config.copy()
        config_options.update(get_config_dict(config, monitor))

        if type == "host":
            new_monitor = Monitors.network.MonitorHost(monitor, config_options)

        elif type == "service":
            new_monitor = Monitors.service.MonitorService(monitor, config_options)

        elif type == "tcp":
            new_monitor = Monitors.network.MonitorTCP(monitor, config_options)

        elif type == "rc":
            new_monitor = Monitors.service.MonitorRC(monitor, config_options)

        elif type == "diskspace":
            new_monitor = Monitors.host.MonitorDiskSpace(monitor, config_options)

        elif type == "http":
            new_monitor = Monitors.network.MonitorHTTP(monitor, config_options)

        elif type == "apcupsd":
            new_monitor = Monitors.host.MonitorApcupsd(monitor, config_options)

        elif type == "svc":
            new_monitor = Monitors.service.MonitorSvc(monitor, config_options)

        elif type == "backup":
            new_monitor = Monitors.file.MonitorBackup(monitor, config_options)

        elif type == "portaudit":
            new_monitor = Monitors.host.MonitorPortAudit(monitor, config_options)

        elif type == "pkgaudit":
            new_monitor = Monitors.host.MonitorPkgAudit(monitor, config_options)

        elif type == "loadavg":
            new_monitor = Monitors.host.MonitorLoadAvg(monitor, config_options)

        elif type == "eximqueue":
            new_monitor = Monitors.service.MonitorEximQueue(monitor, config_options)

        elif type == "windowsdhcp":
            new_monitor = Monitors.service.MonitorWindowsDHCPScope(monitor, config_options)

        elif type == "zap":
            new_monitor = Monitors.host.MonitorZap(monitor, config_options)

        elif type == "fail":
            new_monitor = Monitors.monitor.MonitorFail(monitor, config_options)

        elif type == "null":
            new_monitor = Monitors.monitor.MonitorNull(monitor, config_options)

        elif type == "filestat":
            new_monitor = Monitors.host.MonitorFileStat(monitor, config_options)

        elif type == "dirstat":
            new_monitor = Monitors.host.MonitorDirStat(monitor, config_options)

        elif type == "compound":
            new_monitor = Monitors.compound.CompoundMonitor(monitor, config_options)
            new_monitor.set_mon_refs(m)

        elif type == 'dns':
            new_monitor = Monitors.network.MonitorDNS(monitor, config_options)

        elif type == 'command':
            new_monitor = Monitors.host.MonitorCommand(monitor, config_options)

        else:
            sys.stderr.write("Unknown type %s for monitor %s\n" % (type, monitor))
            continue
        if new_monitor is None:
            continue

        if not quiet:
            print("Adding %s monitor %s: %s" % (type, monitor, new_monitor.describe()))
        m.add_monitor(monitor, new_monitor)

    for i in list(m.monitors.keys()):
        m.monitors[i].post_config_setup()

    return m


def load_loggers(m, config, quiet):
    """Load the loggers listed in the config object."""

    if config.has_option("reporting", "loggers"):
        loggers = config.get("reporting", "loggers").split(",")
    else:
        loggers = []

    for logger in loggers:
        type = config.get(logger, "type")
        config_options = get_config_dict(config, logger)
        if type == "db":
            new_logger = Loggers.db.DBFullLogger(config_options)
        elif type == "dbstatus":
            new_logger = Loggers.db.DBStatusLogger(config_options)
        elif type == "logfile":
            new_logger = Loggers.file.FileLogger(config_options)
        elif type == "html":
            new_logger = Loggers.file.HTMLLogger(config_options)
        elif type == "network":
            new_logger = Loggers.network.NetworkLogger(config_options)
        elif type == "json":
            new_logger = Loggers.file.JsonLogger(config_options)
        else:
            sys.stderr.write("Unknown logger type %s\n" % type)
            continue
        if new_logger is None:
            print("Creating logger %s failed!" % logger)
            continue
        if not quiet:
            print("Adding %s logger %s" % (type, logger))
        m.add_logger(logger, new_logger)
        del(new_logger)
    return m


def load_alerters(m, config, quiet):
    """Load the alerters listed in the config object."""
    if config.has_option("reporting", "alerters"):
        alerters = config.get("reporting", "alerters").split(",")
    else:
        alerters = []

    for alerter in alerters:
        type = config.get(alerter, "type")
        config_options = get_config_dict(config, alerter)
        if type == "email":
            a = Alerters.mail.EMailAlerter(config_options)
        elif type == "ses":
            a = Alerters.ses.SESAlerter(config_options)
        elif type == "bulksms":
            a = Alerters.bulksms.BulkSMSAlerter(config_options)
        elif type == "46elks":
            a = Alerters.fortysixelks.FortySixElksAlerter(config_options)
        elif type == "syslog":
            a = Alerters.syslogger.SyslogAlerter(config_options)
        elif type == "execute":
            a = Alerters.execute.ExecuteAlerter(config_options)
        elif type == "slack":
            a = Alerters.slack.SlackAlerter(config_options)
        elif type == "pushover":
            a = Alerters.pushover.PushoverAlerter(config_options)
        elif type == "nma":
            a = Alerters.nma.NMAAlerter(config_options)
        elif type == "pushbullet":
            a = Alerters.pushbullet.PushbulletAlerter(config_options)
        else:
            sys.stderr.write("Unknown alerter type %s\n" % type)
            continue
        if not quiet:
            print("Adding %s alerter %s" % (type, alerter))
        a.name = alerter
        m.add_alerter(alerter, a)
        del(a)
    return m


def main():
    """This is where it happens \o/"""

    parser = OptionParser()
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False, help="Be more verbose")
    parser.add_option("-q", "--quiet", action="store_true", dest="quiet", default=False, help="Don't output anything except errors")
    parser.add_option("-t", "--test", action="store_true", dest="test", default=False, help="Test config and exit")
    parser.add_option("-p", "--pidfile", dest="pidfile", default=None, help="Write PID into this file")
    parser.add_option("-N", "--no-network", dest="no_network", default=False, action="store_true", help="Disable network listening socket")
    parser.add_option("-d", "--debug", dest="debug", default=False, action="store_true", help="Enable debug output")
    parser.add_option("-f", "--config", dest="config", default="monitor.ini", help="configuration file")
    parser.add_option("-H", "--no-heartbeat", action="store_true", dest="no_heartbeat", default=False, help="Omit printing the '.' character when running checks")
    parser.add_option('-1', '--one-shot', action='store_true', dest='one_shot', default=False, help='Run the monitors once only, without alerting. Require monitors without "fail" in the name to succeed. Exit zero or non-zero accordingly.')
    parser.add_option('--loops', dest='loops', default=-1, help=SUPPRESS_HELP, type=int)

    (options, args) = parser.parse_args()

    if options.quiet and options.verbose:
        options.verbose = False

    if options.quiet and options.debug:
        options.debug = False

    if options.debug and not options.verbose:
        options.verbose = True

    if not options.quiet:
        print("SimpleMonitor v%s" % VERSION)
        print("--> Loading main config from %s" % options.config)

    config = EnvironmentAwareConfigParser()
    if not os.path.exists(options.config):
        print('--> Configuration file "%s" does not exist!' % options.config)
        sys.exit(1)
    try:
        config.read(options.config)
    except Exception as e:
        print('--> Unable to read configuration file "%s"' % options.config)
        print('The config parser reported:')
        print(e)
        sys.exit(1)

    try:
        interval = config.getint("monitor", "interval")
    except Exception:
        print('--> Missing [monitor] section from config file, or missing the "interval" setting in it')
        sys.exit(1)

    pidfile = None
    try:
        pidfile = config.get("monitor", "pidfile")
    except Exception:
        pass

    if options.pidfile:
        pidfile = options.pidfile

    if pidfile:
        my_pid = os.getpid()
        try:
            with open(pidfile, "w") as file_handle:
                file_handle.write("%d\n" % my_pid)
        except Exception:
            sys.stderr.write("Couldn't write to pidfile!")
            pidfile = None

    if config.has_option("monitor", "monitors"):
        monitors_file = config.get("monitor", "monitors")
    else:
        monitors_file = "monitors.ini"

    if not options.quiet:
        print("--> Loading monitor config from %s" % monitors_file)

    m = SimpleMonitor()

    m = load_monitors(m, monitors_file, options.quiet)

    count = m.count_monitors()
    if count == 0:
        sys.stderr.write("No monitors loaded :(\n")
        sys.exit(2)

    if not options.quiet:
        print("--> Loaded %d monitors.\n" % count)

    m = load_loggers(m, config, options.quiet)
    m = load_alerters(m, config, options.quiet)

    try:
        if config.get("monitor", "remote") == "1":
            if not options.no_network:
                enable_remote = True
                remote_port = int(config.get("monitor", "remote_port"))
            else:
                enable_remote = False
        else:
            enable_remote = False
    except Exception:
        enable_remote = False

    if not m.verify_dependencies():
        sys.exit(1)

    if options.test:
        print("--> Config test complete. Exiting.")
        sys.exit(0)

    if options.one_shot:
        print("--> One-shot mode: expecting monitors without 'fail' in the name to succeed,\n     and with to fail. Will exit zero or non-zero accordingly.")

    if not options.quiet:
        print()

    try:
        key = config.get("monitor", "key")
    except Exception:
        key = None

    if enable_remote:
        if not options.quiet:
            print("--> Starting remote listener thread")
        remote_listening_thread = Loggers.network.Listener(m, remote_port, options.verbose, key)
        remote_listening_thread.daemon = True
        remote_listening_thread.start()

    if not options.quiet:
        print("--> Starting... (loop runs every %ds) Hit ^C to stop" % interval)
    loop = True
    heartbeat = 0

    m.set_verbosity(options.verbose, options.debug)
    loops = int(options.loops)

    while loop:
        try:
            if loops > 0:
                loops -= 1
                if loops == 0:
                    print('Ran out of loop counter, will stop after this one')
                    loop = False
            m.run_tests()
            m.do_recovery()
            m.do_alerts()
            m.do_logs()

            if not options.quiet and not options.verbose and not options.no_heartbeat:
                heartbeat += 1
                if heartbeat == 2:
                    sys.stdout.write(".")
                    sys.stdout.flush()
                    heartbeat = 0
        except KeyboardInterrupt:

            if not options.quiet:
                print("\n--> EJECT EJECT")
            loop = False
        except Exception as e:
            sys.exc_info()
            sys.stderr.write("Caught unhandled exception during main loop: %s\n" % e)
        if loop and enable_remote:
            if not remote_listening_thread.isAlive():
                print("Listener thread died :(")
                remote_listening_thread = Loggers.network.Listener(m, remote_port, options.verbose)
                remote_listening_thread.start()

        if options.one_shot:
            break

        try:
            time.sleep(interval)
        except Exception:
            print("\n--> Quitting.")
            loop = False

    if enable_remote:
        remote_listening_thread.running = False
        remote_listening_thread.join(0)

    if pidfile:
        try:
            os.unlink(pidfile)
        except Exception as e:
            print("Couldn't remove pidfile!")
            print(e)

    if not options.quiet:
        print("--> Finished.")

    if options.one_shot:
        ok = True
        print('\n--> One-shot results:')
        for monitor in sorted(m.monitors.keys()):
            if "fail" in monitor:
                if m.monitors[monitor].error_count == 0:
                    print("    Monitor {0} should have failed".format(monitor))
                    ok = False
                else:
                    print("    Monitor {0} was ok (failed)".format(monitor))
            elif "skip" in monitor:
                if m.monitors[monitor].skipped():
                    print("    Monitor {0} was ok (skipped)".format(monitor))
                else:
                    print("    Monitor {0} should have been skipped".format(monitor))
                    ok = False
            else:
                if m.monitors[monitor].error_count > 0:
                    print("    Monitor {0} failed and shouldn't have".format(monitor))
                    ok = False
                else:
                    print("    Monitor {0} was ok".format(monitor))
        if not ok:
            print("Not all non-'fail' succeeded, or not all 'fail' monitors failed.")
            sys.exit(1)


if __name__ == "__main__":
    main()

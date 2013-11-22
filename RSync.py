import os
from subprocess import Popen, PIPE

import sublime
import sublime_plugin

DEFAULT_CONF = {
    'strsync.local_path'        : False,
    'hosts'                     : [ False ],
    'strsync.use_ssh'           : True,
    'strsync.delete_slave'      : True,
    'strsync.remote_is_master'  : True,
    'strsync.excludes'          : [],
}

PREF_PREFIX = 'strsync.'

p = Popen(['which', 'rsync'], stdout=PIPE, stderr=PIPE)
rsyncpath, stderr = p.communicate(None)
if not rsyncpath or stderr or len(rsyncpath) <= 1:
    print( " Can't find rsync ... ") ## not trying too hard, though :)
    rsyncpath = False
else:
    rsyncpath = rsyncpath.decode("utf-8")[:-1]

class RsyncTreeCommand(sublime_plugin.WindowCommand):
    def run(sef):
        # I was trying to do this asynchronously, but this seems to fail ...
        sublime.set_timeout(
            STRSync(sublime.active_window().active_view()).sync_structure(), 
            2)
        

class RsyncFileFromRemoteCommand(sublime_plugin.WindowCommand):
    def run(sef):
        # I was trying to do this asynchronously, but this seems to fail ...
        sublime.set_timeout(
            STRSync(sublime.active_window().active_view()).sync_remote_local(), 
            2)

class RsyncFileToRemoteCommand(sublime_plugin.WindowCommand):
    def run(sef):
        # I was trying to do this asynchronously, but this seems to fail ...
        sublime.set_timeout(
            STRSync(sublime.active_window().active_view()).sync_local_remote(), 
            2)


class RSyncCommand(sublime_plugin.EventListener):
    def on_load_async(self, view):
        STRSync(view).sync_remote_local()
    def on_post_save_async(self, view):
        STRSync(view).sync_local_remote()
    def on_activated_async(self, view):
        pass

class STRSHost(dict):
    def excludes(self):
        return self.get('excludes', [])
    def host_name(self):
        return self.get('remote_host', False)
    def user_name(self):
        return self.get('remote_host', False)
    def path(self):
        return self.get('remote_path', False)

    # def local_path(self):
    #     return self.prefs('local_path')
    # def use_ssh(self):
    #     return self.prefs('use_ssh')
    # def remote_is_master(self):
    #     return self.prefs('remote_is_master')
    # def delete_slave(self):
    #     return self.prefs('delete_slave')

    def remote_path(self, relative_path=''):
        if self:
            path = os.path.normpath(self.get('remote_path','')) + relative_path
            return "{user}{host}{path}".format(
                            user=self['remote_user'] + '@' if self.get('remote_user', False)  else '',
                            host=self['remote_host'] + ':' if self.get('remote_host', False) else '',
                            path=path if self.get('remote_path', False) else '',
                            )
        else:
            return False
            
class STRSync:
    def __init__(self, view=sublime.active_window().active_view()):
        self.view = view

    #################################    
    # settings and rpeferences handling 
    def prefs(self, preference):
        return self.view.settings().get(PREF_PREFIX + preference, DEFAULT_CONF.get(PREF_PREFIX + preference, None))

    def hosts(self):
        for this_host in self.prefs('hosts'):
            yield STRSHost(this_host)
    def main_host(self):
        for this_host in self.hosts():
            if this_host.get('main', False):
                return this_host
        return this_host

    # these are here just to make code shorter and easier to read ...
    def excludes(self):
        return self.prefs('excludes')
    def local_path(self):
        return self.prefs('local_path')
    def use_ssh(self):
        return self.prefs('use_ssh')
    def remote_is_master(self):
        return self.prefs('remote_is_master')
    def delete_slave(self):
        return self.prefs('delete_slave')

    #################################
    # the work itself
    def sync_local_remote(self):
        self.sync_file()

    def sync_remote_local(self):
        self.sync_file(False)

    def sync_file(self, to_server=True):
        # Need to add some checks on whether file changed before syncing
        # right now, we sync way too often...
        local_file = self.view.file_name()
        local_path = self.local_path()
        local_path = os.path.normpath(local_path) if local_path else ''
        if not local_file or not rsyncpath or not local_path:
            return
        if not local_path.upper() in local_file.upper():
            return
        relative_path = local_file[len(os.path.normpath(local_path)) : ]
        for this_host in self.hosts():
            remote_path = this_host.remote_path(relative_path)
            if not remote_path:
                return
            (first, second) = (local_file,remote_path) if to_server else (remote_path, local_file)
            call_params = self.call_params(this_host, to_server, [first, second])
            try:
                self.log('RSync: {}'.format(this_host.host_name()) )
                self.run_rsync(call_params)
            finally:
                self.clear_status

    def sync_structure(self):
        local_file = self.view.file_name()
        local_path = self.local_path()
        local_path = os.path.normpath(local_path) if local_path else ''
        if not local_file or not rsyncpath or not local_path:
            return
        if not local_path.upper() in local_file.upper():
            return
        main_host = self.main_host()
        if main_host:
            remote_path = main_host.remote_path()
            if not remote_path:
                return
            (first, second) = (remote_path + '/', local_path) if self.remote_is_master() else (local_path + '/',remote_path)
            call_params = self.call_params(main_host, True, ['-r', first, second])
            try:
                self.log('RSync: {} [FULL SYNC]'.format(main_host.host_name()) )
                self.run_rsync(call_params)
            finally:
                self.clear_status

    def call_params(self, this_host, to_server=True, others=[]):
        call_params = [rsyncpath ,'-a']
        if self.use_ssh():
            call_params.append('-e ssh')
        if not( to_server and self.remote_is_master()) and self.delete_slave():
            call_params.append('--delete')            
        excludes = self.excludes()
        excludes.extend(this_host.excludes())

        #damn it, I've been coding in perl too long
        excludes = [ item for this_exclude in excludes for item in  ['--exclude', '{}'.format(this_exclude)]] 

        call_params.extend(excludes)
        call_params.extend(others)
        return call_params


    def run_rsync(self,call_params):
        result_mesg = ""
        try:
            p = Popen(call_params, stdout=PIPE, stderr=PIPE)
            stdout, stderr = p.communicate(None)
        except Exception as exc_err:
            result_mesg = " EXCEPTION: \n{}\n".format(exc_err)
        if stderr:
            result_mesg += "RSyncing returned an error: \n{0}\n ... while syncing {1}".format(stderr.decode("utf-8") ," ".join(call_params))
            self.show_panel_message(result_mesg)

    def log(self, message):
        print (message)
        self.view.set_status('_rsync_running', message )

    def clear_status(self):
        self.view.erase_status('_rsync_running')



        
    def show_panel_message(self, message):
        if self.view:
            self.view.output_view = self.view.window().get_output_panel("textarea")
            self.view.window().run_command("show_panel", {"panel": "output.textarea"})
            self.view.output_view.set_read_only(False)
            self.view.output_view.set_syntax_file("Packages/Plain Text/Plain Text.tmLanguage")
            self.view.output_view.run_command("append", {"characters": message})
            self.view.output_view.set_read_only(True)
        print(message)
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
    'strsync.check_remote_git'  : False,
}

# SPINNER_RESOURCES = [
#     '[=       ]',
#     '[ =      ]',
#     '[  =     ]',
#     '[   =    ]',
#     '[    =   ]',
#     '[     =  ]',
#     '[      = ]',
#     '[       =]',
#     ]

PREF_PREFIX = 'strsync.'
annoy_on_rsync_error = True
annoy_on_hash_different = []
git_hash_per_path = {}

def run_executable(call_params):
    result_mesg = ""
    stderr = False
    try:
        p = Popen(call_params, stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate(None)
    except Exception as exc_err:
        result_mesg = " EXCEPTION: \n{}\n".format(exc_err)
    if stderr or result_mesg:
        if stderr:
            result_mesg += "Calling eternal command returned an error: \n{0}\n {1}".format(stderr.decode("utf-8") ," ".join(call_params))
        print (result_mesg)
        return (False, result_mesg)
    else:
        return (True, stdout.decode("utf-8"))

def get_path_for(executable_name):
    (ran_ok, executable_path) = run_executable(['which', executable_name])
    if not ran_ok or not executable_path or len(executable_path) <= 1:
        print( " Can't find {} ... ".format(executable_name)) ## not trying too hard, though :)
        return False
    else:
        return executable_path[:-1]

rsyncpath = get_path_for('rsync')
sshpath = get_path_for('ssh')
gitpath = get_path_for('git')


class RsyncTreeCommand(sublime_plugin.WindowCommand):
    def run(sef):
        STRSync(sublime.active_window().active_view()).sync_structure()


class RsyncFileFromRemoteCommand(sublime_plugin.WindowCommand):
    def run(sef):
        STRSync(sublime.active_window().active_view()).sync_remote_local()

class RsyncFileToRemoteCommand(sublime_plugin.WindowCommand):
    def run(sef):
        STRSync(sublime.active_window().active_view()).sync_local_remote()


class RSyncCommand(sublime_plugin.EventListener):
    def on_load_async(self, view):
        STRSync(view).sync_remote_local()
    def on_post_save_async(self, view):
        STRSync(view).sync_local_remote()
    def on_activated_async(self, view):
        STRSync(view).check_remote_local_git_hash()

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
    def remote_host(self, relative_path=''):
        if self:
            return "{user}{host}".format(
                            user=self['remote_user'] + '@' if self.get('remote_user', False)  else '',
                            host=self['remote_host'] if self.get('remote_host', False) else '',
                            )
        else:
            return False

    def remote_path(self, relative_path=''):
        if self:
            path = os.path.normpath(self.get('remote_path','')) + relative_path
            return "{remote_host}{path}".format(
                            remote_host=self.remote_host(),
                            path=':'+ path if self.get('remote_path', False) else '',
                            )
        else:
            return False

class STRSync:
    def __init__(self, view=sublime.active_window().active_view()):
        self.view = view
        self.remote_hash = False
        # self.spinner_step = 1
        # self.spinner_direction = 1
        # self.spinner_running = False

    #################################
    # settings and preferences handling
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
    def check_remote_local_git_hash(self):
        if not self.prefs('check_remote_git'):
            return
        (ran_ok, local_hash) = run_executable([gitpath, 'rev-parse', 'HEAD'])
        if not ran_ok:
            raise Exception(local_hash)
        (ran_ok, self.remote_hash) = run_executable(
                                    [
                                        sshpath, 
                                        self.main_host().remote_host(), 
                                        'cd {}; git rev-parse HEAD'.format(self.main_host().path()),
                                    ])
        if not ran_ok:
            raise Exception(self.remote_hash)
        if self.remote_hash in annoy_on_hash_different:
            return
        if self.remote_hash != local_hash:
            print ("Remote Git hash ({}) is diferent from local ({})".format(self.remote_hash, local_hash))
            self.view.window().show_quick_panel(
                        [
                            'Remote Git hash is diferent from local hash. FULL Rsync ?', 
                            'No, don''t RSync just now. (This can get annoying)'
                        ],
                        lambda s: self.handle_hash_is_different(s),
                        selected_index=1,
                            )

    def handle_hash_is_different(self, answer):
        if answer in [0, 1]:
            annoy_on_hash_different.append(self.remote_hash)
        if answer == 0:
            self.sync_structure()

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
            self.log_status('RSync: {}'.format(this_host.host_name()) )
            self.run_rsync(call_params)

    def sync_structure(self):
        if not self.valid_file_to_process():
            return
        local_file = self.view.file_name()
        local_path = self.local_path()

        main_host = self.main_host()
        if main_host:
            remote_path = main_host.remote_path()
            if not remote_path:
                return
            (first, second) = (remote_path + '/', local_path) if self.remote_is_master() else (local_path + '/',remote_path)
            call_params = self.call_params(main_host, not self.remote_is_master(), ['-r', first, second])
            self.log_status('RSync: {} [FULL SYNC: Please wait ... ]'.format(main_host.host_name()) )
            sublime.set_timeout_async(lambda: self.run_rsync(call_params), 10)

    def call_params(self, this_host, to_server=True, others=[]):
        call_params = [rsyncpath ,'-a']
        if self.use_ssh():
            call_params.append('-e ssh')
        if not( to_server and self.remote_is_master()) and self.delete_slave():
            call_params.append('--delete')
        excludes = self.excludes()
        excludes.extend(this_host.excludes())

        # damn it, I've been coding in perl too long
        # this will introduce a '--exclude' for each excluded path.
        # for a list such as [ '/bla/ble', '/doo/bi', '/a/b/'], the end result 
        # will be something like ['--exclude', '/bla/ble','--exclude', '/doo/bi', '--exclude', '/a/b/']
        excludes = [ item for this_exclude in excludes for item in  ['--exclude', '{}'.format(this_exclude)]] 

        call_params.extend(excludes)
        call_params.extend(others)
        return call_params


    def run_rsync(self,call_params):
        global annoy_on_rsync_error
        (rsynced_ok, strMessage) = run_executable(call_params)
        if not rsynced_ok:
            if annoy_on_rsync_error:
                self.log_error_message(strMessage)
                self.view.window().show_quick_panel(
                        [
                            'Stop annoying me, for now, about network errors (a successful RSync will reset this) ', 
                            # 'Ignore network errors for this Sublime session (you''ll need to reload to reset this)', 
                            'Oh... golly! Please poke me each time this happens.'
                        ],
                        lambda s: self.handle_error_reponse(s),
                        selected_index=0,
                            )
        else:
            annoy_on_rsync_error = True
        print ("End rsync ")
        self.clear_status()

    def handle_error_reponse(self, answer):
        global annoy_on_rsync_error
        if answer == 0:
            annoy_on_rsync_error = False


    def log_status(self, message):
        print (message)
        self.view.set_status('_rsync_running{}'.format(self), message )
        # self.start_spinner()

    def clear_status(self):
        old_status = self.view.get_status('_rsync_running{}'.format(self))
        self.view.set_status('_rsync_running{}'.format(self), 'Ended [{}]  '.format(old_status))
        # self.stop_spinner()
        sublime.set_timeout_async(lambda: self.view.erase_status('_rsync_running{}'.format(self)), 2000)
        

    # def stop_spinner(self):
    #     self.spinner_running = False
    # def start_spinner(self):
    #     self.spinner_running = True
    #     sublime.set_timeout_async(lambda: self.progress_spinner(), 100)

    # def progress_spinner(self):
    #     print ("running")
    #     if not self.spinner_running :
    #         self.view.erase_status('__rsync_spinner{}'.format(self))
    #         return

    #     self.spinner_step += self.spinner_direction
    #     if self.spinner_step in [-1 , len(SPINNER_RESOURCES)]:
    #         self.spinner_direction = self.spinner_direction * -1
    #         self.spinner_step += self.spinner_direction * 2
    #     self.view.set_status('__rsync_spinner{}'.format(self), SPINNER_RESOURCES[self.spinner_step] )
    #     sublime.set_timeout_async(lambda: self.progress_spinner(), 100)


    def log_error_message(self, message):
        if self.view:
            self.view.output_view = self.view.window().get_output_panel("textarea")
            self.view.window().run_command("show_panel", {"panel": "output.textarea"})
            self.view.output_view.set_read_only(False)
            self.view.output_view.run_command("append", {"characters": message})
            self.view.output_view.set_read_only(True)
        print(message)
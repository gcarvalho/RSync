# RSync for Sublime Text 3

This is a Sublime Text plugin to synchronise files with a remote server using [rsync](http://en.wikipedia.org/wiki/Rsync). RSync is a whole lot faster and more eficient than copying everything, since it tries to identify the diferences and synchronise only these diferences.

#####** THIS A RAW, UNTESTED PLUGIN **
This cannot be emphasized enough. 

I use it for my daily work, but I have tested it very little outside of my workflow.
If this plugins erases all your files, breaks your heart and elopes with you pet cactus, don't come crying to me.

In time, I'll add to this document better instructions, but for now this is what you get.

##Features

- Uses rsync (kinda obvious) over ssh (optionally)
- Suports multiple hosts
- Supports excludiing certain file patterns

## Dependencies
- You must have rsync installed, somewhere that "which rsync" will find it
- You must have ssh setup, if you want to use it

**WINDOWS USERS**: Sorry guys, this was written in a day and I haven't had a chance to even try to get it working on windows. Feel free to take a shot at getting it to work on windows and sending me the pull request.

## Installing it
There are 2 ways install this plugin, none of which I'll explain, but I'll list them:

1. Just use [Package Manager](https://sublime.wbond.net/)
1. Clone this repository into the Packages folder of your Sublime Text instalation. 

 You can find the Packages folder by having a look at your preferences menu.

## Configuration
Have a look at the [example settings](./RSync.sublime-settings).
I recomend you do them in the project file for your work, rather then the general settings file.

## Using it 
After configuration is done, go to the Tools menu => RSync => Synchronise the whole tree.
This will take a while, if your project is very big. Don't worry, it will be a lot faster after this first time.

Now change a file and save it. If properly setup (and if you didn't stumble on an unknown bug), ot should show up on your remote host.


## To do
- Lots
- add some more checks to try and stop you from overwriting changes that you want to keep
- add hooks for running commands before/after sync
- add more settings to be both general and by host
- improve eficiency: we're calling rsync --way-- too aften
- sync tree on project open
- some sort of configuration wizard would be nice...
- add a "don't bug me for now" on error. When away from a network, saving gets annoying...
- **Improve documentation**
- Seriously, lots more...

# SyncToGit

## Table of contents
1. [Introduction](#introduction)
1. [How To Install](#how-to-install)
1. [Known problems](#known-problems)
1. [License](#license)

## Introduction

This is a lightweight backup solution for your Evernote® stuff. It syncs your notes with their resources to the git repository in HTML format.

Say, you have the following in your Evernote:
![Evernote screenshot](http://KostyaEsmukov.github.io/SyncToGit/images/ev.png)

This is a tree of resulting git repository:  
```
├── index.html
├── Notes
│   ├── dsf
│   │   └── First Notebook
│   │       ├── Encrypted example.d9c1deac-2d62-405d-a5fc-26599e4e6a51.html
│   │       ├── fd _002f _005c _0022 _0027 пва .txt.ab05137e-5788-47ed-831f-6af475b94ad5.html
│   │       ├── Getting Started.6f5d93dd-4db9-4b0d-a343-c0d4eb5ed35b.html
│   │       ├── Δ_002c Й_002c ק_002c م_002c _0e57_002c あ_002c 叶_002c 葉_002c and 말..211590e3-98bc-46bc-bfa9-d52da889514b.html
│   │       ├── Δ_002c Й_002c ק_002c م_002c _0e57_002c あ_002c 叶_002c 葉_002c and 말..7b7a3ab8-f458-4163-98b4-e6ad5c8d20c1.html
│   │       └── ТУДУ.6cab5a3c-abcc-4457-80e6-211388093bec.html
│   └── отрипмакпенр арв
│       └── ваат.da8d3c90-8f0b-440f-9b46-3c748f1bef65.html
└── Resources
    ├── 6f5d93dd-4db9-4b0d-a343-c0d4eb5ed35b
    │   ├── 0e2d61050811670832d80ed457203343.png
    │   ├── 4914ced8925f9adcc1c58ab87813c81f.png
    │   ├── 53df38a9b4999d2f9ababedaae41d3b0.png
    │   ├── 836fc57702fc08596a5b6d74e54b33cc.png
    │   ├── 908ca278561900d6620da9a8b06ecbaf.png
    │   ├── 950bf3517b1e7f23bc40066853a23f7e.png
    │   ├── bb54c12582d7d1793fb860ae27fe9daa.png
    │   ├── c7dbb1ce10ff3dfe7c0a485d904d0d23.png
    │   └── e9a7b8ccbfaeca2feebc51ccb1faa2b6.png
    ├── ab05137e-5788-47ed-831f-6af475b94ad5
    │   ├── c1506a96c01707c542581221e63e7bb8.mpeg
    │   └── f1f8a2cf00c9b9765f30ca904281290e.pdf
    └── da8d3c90-8f0b-440f-9b46-3c748f1bef65
        └── d2a99d1e273b2fc81b32c4d0fa3216ad.png
```
Git log:  
![Git log screenshot](http://KostyaEsmukov.github.io/SyncToGit/images/git.png)  
###[See the result online](http://KostyaEsmukov.github.io/SyncToGit/example/)  

## How To Install:
1. You should have `git` installed.  
    - Windows:  
    http://git-scm.com/download/win
    - Debian\Ubuntu:  
    \# `apt-get install git`
1. Make sure you have Python 2.7 installed with virtualenv extension.  
    - Windows:  
        * Download installer from https://www.python.org/downloads/ , install it.  
        * Open cmd  (Win+R, cmd, Enter)  
        * \> `cd \Python27\Scripts`  
        * \> `pip install virtualenv`  
    - Debian\Ubuntu:  
        * \# `apt-get install python python-virtualenv`
1. Create a directory anywhere you like for this program.  
    Examples: `/opt/synctogit` (Linux); `%USERPROFILE%\synctogit` (Windows).
1. Set up a virtual environment and install required dependencies:  
    - Windows:  
        * \> `cd %USERPROFILE%\synctogit`  
        * \> `C:\Python27\Scripts\virtualenv.exe . --no-site-packages --setuptools`  
        * \> `Scripts\activate`  
    - Linux:  
        * $ `cd /opt/evernotetogit`  
        * $ `virtualenv . --no-site-packages --setuptools`  
        * $ `. ./bin/activate`  
    - Both:  
        * `pip install oauth2 GitPython defusedxml regex`  
        * `deactivate`  

1. `git clone https://github.com/KostyaEsmukov/SyncToGit.git`
1. `cd SyncToGit`
1. Create a new file in this folder: `config.ini`

    ```ini
    [git]
    repo_dir = /home/user/EvernoteBackup
    push = false
    ```
`repo_dir` - absolute path to the directory where you would like to keep your target git repository with synced notes. This folder must exist (and should be empty).  
`push` - should program push changes to remotes?  
1. You are all set. Run the program:  
    - Windows:  
        * \> `..\Scripts\python main.py config.ini`  
    - Linux:  
        * $ `../bin/python main.py config.ini`  

    Git repository will be initialized and you will be guided through authorization steps. After it initial sync will be performed. Authorization token will be saved in `config.ini`, so keep this file secure!  
Following syncs will use that token until it is expired or revoked.
You can run the sync this way:  
    - Windows:  
        * \> `..\Scripts\python main.py config.ini -b`  
    - Linux:  
        * $ `../bin/python main.py config.ini -b`  

    Notice the `-b` key - this means never prompt anything - so-called batch mode.
1. Now you can add remotes to your git repository if you want. Just cd to it and add remotes as usual. Make sure to set `push = true` in the `config.ini` file.
1. Create a sheduler task, so syncs are performed automatically.
    - Linux:
        * $ `crontab -e`
        * Add new line: `*/10 * * * * /opt/synctogit/SyncToGit/sync.sh`
        * All errors occured during syncs will be mailed to your account by cron. Please refer to its manual.
    - Windows:  
        * Create new task:   
        \> `Schtasks /Create /TN synctogit /SC DAILY /TR "%USERPROFILE%\synctogit\SyncToGit\NoShell.vbs %USERPROFILE%\synctogit\SyncToGit\sync.bat" /RI 10`
        * you may want to adjust it. Navigate to **Control Panel** -\> **Task Sheduler** -\> **synctogit**
        * All errors occured during syncs will be saved in `%USERPROFILE%\synctogit\SyncToGit\errors.out` file. Make sure to check it sometimes.


## Known problems:
* IE has problems with opening notes containing non-latin (unicode) chars. Google Chrome and Mozilla Firefox hasn't.
* Some Evernote clients (ex. ios) make note's html look ugly. This makes diff harder to read. Not a big deal.




## License
MIT

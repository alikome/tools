#!/usr/bin/env bash
set -euo pipefail

# Functions

mainMenu ()
{
    echo -e "\033[36m""Apps Updater""\e[0m"
    echo "1 Install Jackett"
    echo "2 Install Sonarr"
    echo "3 Install Radarr"
    echo "4 Install Syncthing"
    echo "q Quit"
}

installJackett () # Jackett installer function
{
            echo "Getting Jackett..."
            wget -qO ~/Jackett.tar.gz $(curl -s https://api.github.com/repos/Jackett/Jackett/releases/latest | grep 'browser_download_url' | grep 'LinuxAMDx64' | cut -d\" -f4 | tail -n 1)
            echo "Extracting and configuring Jackett..."
            tar xf ~/Jackett.tar.gz
            rm ~/Jackett.tar.gz
            echo "Starting up Jackett..."
            screen -dmS jackett /bin/bash -c 'export TMPDIR=~/tmp; cd ~/Jackett; ./jackett_launcher.sh --NoUpdates'
}

installSyncthing () # Syncthing installer function
{      
            rm -rf Syncthing
            version=$(curl -s https://api.github.com/repos/syncthing/syncthing/releases/latest | grep tag_name | cut -d\" -f4)
            echo "Getting Syncthing " $version
            wget -qO ~/Syncthing.tar.gz https://github.com/syncthing/syncthing/releases/download/$version/syncthing-linux-amd64-$version.tar.gz
            echo "Extracting and configuring Syncthing..."
            tar xf ~/Syncthing.tar.gz
            mv "syncthing-linux-amd64-$version" "Syncthing"
            rm ~/Syncthing.tar.gz
            echo "Starting up Syncthing..."
            screen -dmS syncthing ~/Syncthing/syncthing
}


while [[ 1 ]]
do
    echo
    mainMenu
    echo
    read -ep "Enter the number of the option you want: " CHOICE
    echo
    case "$CHOICE" in
        "1") # Install Jackett
            if pgrep -f Jackett > /dev/null
            then
            echo "Removing Jackett"
            pkill -f Jackett
            rm -rf Jackett
            installJackett
            else
            installJackett
            fi 
            echo
            ;;
        "2") # Install Sonarr
            echo "Removing Sonarr"
            pkill -f Sonarr
            rm -rf Sonarr
            echo "Getting Sonarr..."
            wget -qO ~/Sonarr.tar.gz 'https://services.sonarr.tv/v1/download/main/latest?version=4&os=linux&arch=x64'
            echo "Extracting and configuring Sonarr..."
            tar xf ~/Sonarr.tar.gz
            rm ~/Sonarr.tar.gz
            echo "Starting up Sonarr..."
            screen -dmS Sonarr /bin/bash -c 'export TMPDIR=~/tmp; mono --debug Sonarr/Sonarr.exe'
            echo
            ;;
        "3") # Install Radarr
            echo "Removing Radarr"
            pkill -f Radarr
            rm -rf Radarr
            echo "Getting Radarr..."
            wget -qO ~/Radarr.tar.gz 'https://radarr.servarr.com/v1/update/master/updatefile?os=linux&runtime=netcore&arch=x64'
            echo "Extracting and configuring Radarr..."
            tar xf ~/Radarr.tar.gz
            rm ~/Radarr.tar.gz
            echo "Starting up Radarr..."
            screen -dmS Radarr /bin/bash -c 'export TMPDIR=~/.config/Radarr/tmp; ~/Radarr/Radarr -nobrowser'
            echo
            ;;
        "4") # Install Syncthing
            if pgrep -f 'Syncthing' > /dev/null
            then
            echo "Removing Syncthing"
            pkill -f Syncthing
            installSyncthing
            else
            installSyncthing
            fi
            echo
            ;;    
        "q") # quit the script entirely
            exit
            ;;
    esac
done

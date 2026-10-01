# Setting up the Odds Board

About an hour, mostly waiting on installs. You'll type commands, but you won't write any code.
Commands go in a terminal on the Pi (step 3 shows how to get one). Copy and paste them exactly.

Parts: Raspberry Pi 3A+, Adafruit RGB Matrix Bonnet, 64x32 HUB75 panel, 5V 4A power supply,
microSD card (16GB+), heatsink, 2x20 header extender.

---

## 1. Prepare the microSD card (on your computer)

1. Install **Raspberry Pi Imager** from raspberrypi.com/software and open it.
2. Device: **Raspberry Pi 3**. OS: **Raspberry Pi OS (other) -> Raspberry Pi OS Lite (64-bit)**. Storage: your card.
3. When it asks about OS customisation, choose **Edit settings** and fill in:
   - Hostname: `oddsboard`
   - Username and password: pick your own (the examples below use `joe`)
   - Wi-Fi name and password
   - Time zone: **America/New_York**
   - Services tab: turn on **Enable SSH** (password authentication)
4. Write the card, put it in the Pi.

## 2. Put the hardware together

1. Stick the heatsink on the Pi's processor.
2. Press the header extender onto the Pi's pins, then the Bonnet onto the extender.
3. Connect the panel's ribbon cable to the Bonnet and to the panel's **input** side (arrows on the
   panel point away from the input).
4. Connect the panel's power leads to the Bonnet's screw terminals (red to +, black to -).
5. Plug the 5V 4A supply into the **Bonnet's** barrel jack. It powers the Pi too, so don't also
   plug the Pi in by USB.

Give it 2 minutes to boot the first time.

## 3. Connect to the Pi

On Windows, open **PowerShell** (on a Mac, **Terminal**) and type, using your username:

    ssh joe@oddsboard.local

Type `yes` if asked, then your password. You're now typing on the Pi.
(MobaXterm, which the plane tracker guide recommends, works too.)

## 4. Panel library (same proven steps as the plane tracker)

Install the build tools and the panel library:

    sudo apt-get update
    sudo apt-get install -y git python3-dev python3-pip python3-pillow cython3 python3-setuptools build-essential unzip
    cd ~
    git clone https://github.com/hzeller/rpi-rgb-led-matrix.git
    cd rpi-rgb-led-matrix
    make

Give the Pi 3A+ more working memory for the next step (otherwise it can crash mid-install):

    sudo apt-get install -y dphys-swapfile
    sudo dphys-swapfile swapoff
    echo "CONF_SWAPSIZE=512" | sudo tee /etc/dphys-swapfile
    sudo dphys-swapfile setup
    sudo dphys-swapfile swapon

Run Adafruit's Bonnet setup:

    cd ~
    sudo pip3 install adafruit-python-shell --break-system-packages
    wget https://github.com/adafruit/Raspberry-Pi-Installer-Scripts/raw/main/rgb-matrix.py
    python3 -m venv --system-site-packages env
    source env/bin/activate
    sudo -E env PATH=$PATH python3 rgb-matrix.py

When the script asks:
- Interface board: **Bonnet** (option 1)
- **Convenience** (choose Quality only if you soldered the GPIO 4-18 bridge)
- Let it reboot when it finishes, then reconnect (step 3).

Make the library available everywhere:

    sudo cp -r ~/env/lib/python3.*/site-packages/rgbmatrix /usr/lib/python3/dist-packages/
    python3 -c "import rgbmatrix; print('ok')"

You must see `ok`. If not, stop and ask for help.

## 5. Test the panel

    cd ~/rpi-rgb-led-matrix/examples-api-use
    make
    sudo ./demo -D 1 runtext.ppm --led-rows=32 --led-cols=64 --led-limit-refresh=60 --led-slowdown-gpio=2 --led-gpio-mapping=adafruit-hat

You should see scrolling "HELLO WORLD". Press Ctrl+C to stop. If the picture is broken or in the
wrong place, reseat the Bonnet and try again. Don't continue until this works.
(Colors swapped? That's fine - fix it later under Settings -> LED color order.)

## 6. Install the odds board

Download the project from GitHub (use your own GitHub username in the address):

    cd ~
    git clone https://github.com/YOUR-GITHUB-NAME/odds-board.git
    cd odds-board
    bash install.sh

If your GitHub repository is **private**, git will ask for a username and password. Use your
GitHub username, and for the password a personal access token (GitHub -> Settings -> Developer
settings -> Personal access tokens -> Fine-grained, read-only access to this one repository).

The installer checks the panel library, installs what it needs, sets up auto-start, and starts the
board. It ends by printing the web address.

Optional: turn the extra memory back off to spare the SD card:

    sudo dphys-swapfile swapoff
    sudo systemctl disable dphys-swapfile

## 7. First-time settings

Open **http://oddsboard.local:8080** on your phone or computer, go to **Settings**:
- Weather location (lat,lon) and your **Tomorrow.io** key (free at tomorrow.io)
- Track: Saratoga or Belmont
- Save, then **Restart display**

Done. The board shows clock and weather, and switches to the race board 90 minutes before post.

---

## Handy commands (on the Pi)

    sudo systemctl status odds-board      # is it running?
    sudo systemctl restart odds-board     # restart it
    sudo systemctl stop odds-board        # stop it (e.g. to run it by hand)
    journalctl -u odds-board -n 50        # recent log lines (also on the web Logs page)

## Updating to a new version

After new changes are pushed to GitHub:

    cd ~/odds-board
    git pull
    bash install.sh

Your settings and API key are kept (they're never stored in git).

## If something's wrong

- **Web page won't load:** wait a minute after power-up; check `sudo systemctl status odds-board`.
- **Panel flickers:** Settings -> GPIO slowdown, try 3 or 4, Save, Restart display.
- **Colors wrong:** Settings -> LED color order (RBG is the common fix).
- **No race board on a race day:** check Settings -> Track, and the Board page for an error message.
- **Anything else:** copy the output of `journalctl -u odds-board -n 50` into the chat.

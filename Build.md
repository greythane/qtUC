<!-- PROJECT LOGO -->
<br/>
<p align="center">
  <a href="https://github.com/greythane/qtUC">
    <img height="100" width="100" src="images/radio.png" alt="Logo">
  </a>

  <h1 align="center">qtUC (USRP Client)</h1>

  <p align="center">
    qtUC is a GUI application for accessing amateur radio digital networks from your PC
    <br />
    <br />
    <a href="https://github.com/greythane/qtUC/issues">Report Bug</a>
    ·
    <a href="https://github.com/greythane/qtUC/issues">Request Feature</a>
  </p>
</p>



## Introduction
The qtUC python application is a GUI front end for accessing ham radio digital networks from your PC.  
It is the front end app for the DVSwitch suite of software and connects to the Analog_Bridge component.

## Features
The user can:

 - Select digital network
 - Select "talk group" or reflector from a list
 - Transmit and receive to the network using their speakers and mic
 - Record a list of stations received in the session
 - See pictures of the hams from QRZ.com
 - Themeable

## Building from source
### Prerequisites
You will need to download or clone the repository at [https://github.com/greythane/qtUC](https://github.com/greythane/qtUC)

A native install of Python can be used but it is strongly recommended that a virtual environment be used for development  
My development environment uses Visual Studio Code with pyenv and pyenv-virtualenv for Python and packages. Using a virtual evnironment allows for different versions of Python and dependancies to be used without interferring with any local Python installation and dependancies    

[Real python](https://realpython.com/intro-to-pyenv/) has a good introduction to pyenv and how to install and use it for development  

### Build instructions to run from source by platform:

- ###Windows 10

    Install [pyenv-win](https://pyenv-win.github.io/pyenv-win/) following the instructions on the pyenv-win site  

    Open command or powershell      
    *Install the development Python*  
    **pyenv install 3.8.2**  *(or your preferred Python version)*  
    
    *pyenv-virtualenv is not yet available for Windows so virtualenv is used if desired.  
    Note: As Windows does not normally use a system Python, the virtualenv may not be needed*  
     
    **cd 'my repo directory'  
    pyenv local 3.8.2  
    python -m pip install –user virtualenv   
    python -m venv env  
    .\env\Scripts\activate**    *(this actvates the virtual environment)*    

    *Clone the qtUC repository and change to the directory*   
    **git clone https://github.com/greythane/qtUC.git  
    cd 'my repo path'/qtUC**   
    
	 *Install required dependencies*   
    Download PyAudio from [https://www.lfd.uci.edu/~gohlke/pythonlibs/](https://support.microsoft.com/en-us/help/2977003/the-latest-supported-visual-c-downloads) for your version (32 or 64 bit)
 
    **pip install PyAudio-0.2.11-cp37-cp37m-win_XXX.whl   
    pip install bs4  
    pip install Pillow  
    pip install requests  
    pip install PyQt5**  
    
    You should now be ready to run qtUC in the devoplemt environment
    
    If you get an error about MSVCP140.DLL, then you will need to install the MSVC C++ runtime library.  
    Get it from: [https://support.microsoft.com/en-us/help/2977003/the-latest-supported-visual-c-downloads](https://support.microsoft.com/en-us/help/2977003/the-latest-supported-visual-c-downloads)  
[Back To Top][top]
 
- ###Linux  
	 This assumes that git and necessary dependancies are already installed  
	 
    *Open a command prompt and install pyenv*  
    An automated [pyenv-installer] (https://github.com/pyenv/pyenv-installer) is available to assist painless installation on the common Linux systems  
    **curl https://pyenv.run | bash**  
    
    *Or manual installation if required*  
>     git clone https://github.com/pyenv/pyenv.git $HOME/.pyenv**  
>      
>     echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc  
>     echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc  
>     echo -e 'if command -v pyenv 1>/dev/null 2>&1; then\n eval "$(pyenv init -)"\nfi' >> ~/.bashrc  

    *Install pyenv-virtualenv*  
    **git clone https://github.com/pyenv/pyenv-virtualenv.git $(pyenv root)/plugins/pyenv-virtualenv  
    echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.bashrc**
    
    *Install Python and create a virtual environment*  
    **pyenv install 3.8.2**  *(or your preferred Python version)*  
    **pyenv virtualenv 3.8.2 dev**  *(create your development environment 'dev')*
    
    *Clone the qtUC repository and change to the directory*   
    **cd 'my repo path'  
    git clone https://github.com/greythane/qtUC.git  
    cd 'my repo path'/qtUC**   

	 *Initialise the development environment*  
    **pyenv local dev**  
    
    *Install system dependencies*
    **sudo apt-get install python3-pyaudio  
    sudo apt-get install portaudio19-dev  
    sudo apt-get install python3-pil.imagetk**  
    
    You should now be ready to run qtUC in the devoplemt environment  
[Back To Top][top]  

- ###Mac
    
    *Install Hombrew if required*  
    **ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"**  
    
    *With Homebrew installed*  
    **brew install pyenv  
    brew install pyenv-virtualenv   
    brew install portaudio**  
      
    *Install Python and create a virtual environment*  
    **pyenv install 3.8.2**  *(or your preferred Python version)*  
    **pyenv virtualenv 3.8.2 dev**  *(create your development environment 'dev')*
    
    *Clone the qtUC repository and change to the directory*   
    **cd 'my repo path'  
    git clone https://github.com/greythane/qtUC.git  
    cd 'my repo path'/qtUC**   
    
    *Initialise the development environment and install dependencies*  
    **pyenv local dev
    pip3 install pyaudio  
    pip3 install PyQt5  
    pip3 install bs4 Pillow requests**  
     
    You should now be ready to run qtUC in the devoplemt environment
[Back To Top][top]

<!-- CONTRIBUTING -->
## Contributing
Contributions are what make the open source community such an amazing place to be learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<!-- CONTACT -->
## Contact

VK3VW (Rowan) - [Github](https://github.com/greythane) | [Email](mailto:greythane@gmail.com)

Project Link: [https://github.com/greythane/qtUC](https://github.com/greythane/qtUC)

## Related projects
[DVSwitch](https://dvswitch.groups.io), [USRP_Client (pyUC)] (https://github.com/DVSwitch/USRP_Client)

[Back To Top][top]

## Licensing
This software is for use on amateur radio networks only, it is to be used  
for educational purposes only. Its use on commercial networks is strictly   
prohibited.  Permission to use, copy, modify, and/or distribute this software   
hereby granted, provided that the above copyright notice and this permission   
notice appear in all copies.  

THE SOFTWARE IS PROVIDED "AS IS" AND DVSWITCH DISCLAIMS ALL WARRANTIES WITH  
REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY  
AND FITNESS.  IN NO EVENT SHALL N4IRR BE LIABLE FOR ANY SPECIAL, DIRECT,  
INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM  
LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE  
OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR  
PERFORMANCE OF THIS SOFTWARE.  

[Back To Top][top]

<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[top]: #top

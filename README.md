# OpenScan Image Cropper

OpenScan Image Cropper is a Python-based GUI tool designed to crop images based on brightness levels. It features live preview, interactive threshold selection (including region-based and darkest-image options), and batch processing capabilities.

## Features

- **Live Preview:** Displays a preview of your image with panning and zooming.
- **Threshold Selection:**  
  - **Region Selection:** Set the threshold by selecting a region on the image.  
  - **Darkest Image Analysis:** Automatically load the darkest image from the folder to help determine a suitable threshold.
- **Batch Processing:** Process all images in a folder with a progress bar.
- **Single Image Processing:** Process only the currently displayed image.
- **Custom Output Options:**  
  - Custom file prefix.  
  - Choice of output file format (Original, TIFF, PNG, JPG).

## Prerequisites

### To Run the Source Code
- **Python 3.x**
- Install required packages:
  ```bash
  pip install opencv-python Pillow
Tkinter is usually included with Python on Windows.

For the Executable
No additional prerequisites are required.
Note: The EXE may trigger warnings from Windows Defender (or similar antivirus software) if it is unsigned. Users might need to allow the file manually.
How to Use
Running from Source:
Open a command prompt in the project folder and run:
bash
Copy
python OpenScanImageCropper.py

Using the Executable:
Download and run the EXE file. If Windows Defender flags the file, choose to allow or unblock it.
Building the Executable
To create a standalone executable, use PyInstaller:

bash
Copy
pyinstaller --onefile --windowed OpenScanImageCropper.py
Troubleshooting
Large File Warnings:
GitHub may warn you about large files (EXE and package files). For distribution, consider using GitHub Releases or Git Large File Storage (LFS).

Antivirus Warnings:
Unsigned executables may trigger warnings. Consider code signing your application if you plan on public distribution.


Contributing
Contributions and feedback are welcome! Please fork the repository and submit pull requests.


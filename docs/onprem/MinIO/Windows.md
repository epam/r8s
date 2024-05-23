# MinIO Installation & Configuration on Windows

#### Using PowerShell (as an Administrator):

- Make a directory to save MinIO binary files:

  ```powershell
  PS> mkdir "C:\Program Files\Minio"
  ```

- Download the latest version of MinIO server to the created folder:

  ```powershell
  PS> Invoke-WebRequest -Uri "https://dl.min.io/server/minio/release/windows-amd64/minio.exe" -OutFile "C:\Program Files\Minio\minio.exe"
  ```

- Download the latest version of MinIO client to the created folder:

  ```powershell
  PS> Invoke-WebRequest -Uri "https://dl.minio.io/client/mc/release/windows-amd64/mc.exe" -OutFile "C:\Program Files\Minio\mc.exe"
  ```

- Add the directory with executables to `PATH` environment variable:

  ```powershell
  PS> setx PATH "$Env:PATH;C:\Program Files\Minio"
  ```

#### Manually:

- Go to the [link](https://min.io/download#/windows) and download the latest versions of MinIO server `minio.exe` and MinIO client `mc.exe`.
- Put the files into the convenient for you folder and add the folder path to `PATH` environment variable by executing the command from the section above. Or you can do this using Windows UI (My computer -> Properties -> Advanced System Settings -> Environment Variables);

To check whether the program was successfully installed, go the PowerShell and execute:

```powershell
PS> minio -h # to check if the server is available
PS> mc -h  # to check if the client is available
```

### Configuration MinIO:

Open Windows PowerShell and perform the following steps:

- Export your credentials for MinIO server:

  ```powershell
  PS> setx MINIO_ROOT_USER {YOUR_USER_NAME}
  PS> setx MINIO_ROOT_PASSWORD {YOUR_USER_PASSWORD}
  ```

  *Note:* in order to get Windows environment variables applied you may have to close and then reopen your terminal.

- Start MinIO server on local machine:

  ```powershell
  PS> minio server /minio --console-address 0.0.0.0:41149
  ```

- Open new terminal and configure your MinIO client to give it access to the local server (put the url to your local server in the command below):

  ```powershell
  PS> mc alias set myminio http://MINIO-SERVER $Env:MINIO_ROOT_USER $Env:MINIO_ROOT_PASSWORD
  ```
  *Note:* with the command above you've created a profile named `myminio`. The next configuration actions must be performed from this profile since it's connected to your local server.
  
- Make up your own access key and secret key for a user which will be used in RightSizer application (length must be greater than 8):

  ```powershell
  PS> setx MINIO_ACCESS_KEY {YOUR_ACCESS_KEY}
  PS> setx MINIO_SECRET_ACCESS_KEY {YOUR_SECRET_KEY}
  ```

  Don't forget to reload the terminal.

- Create MinIO user with you just set access keys:

  ```powershell
  PS> mc admin user add myminio $Env:MINIO_ACCESS_KEY $Env:MINIO_SECRET_ACCESS_KEY
  ```

* Assign the policy `consoleAdmin`  to the created user to make him be able to perform various commands:

  ```powershell
  PS> mc admin policy attach myminio consoleAdmin --user $Env:MINIO_ACCESS_KEY
  ```
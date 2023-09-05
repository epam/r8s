## MongoDB Installation & Configuration on Windows

### Installation:

- Download installer from [link](https://www.mongodb.com/try/download/community?tck=docs_server);
- Run the MongoDB installer (for example, from the Windows Explorer/File Explorer: 
go to the directory where you downloaded the MongoDB installer (.msi file), by default, this is your Downloads directory.
Double-click the .msi file.);
- Follow the MongoDB Community Edition installation wizard:
1. Choose Setup Type. You can choose either the Complete (recommended for 
   most users) or custom 
   setup type. The Complete setup option installs MongoDB and the MongoDB tools to the default location. The Custom setup option allows you to specify which executables are installed and where;
2. Service Configuration. Starting in MongoDB 4.0, you can set up MongoDB as a Windows service during the installation or just install the binaries;
3. Select Install MongoD as a Service MongoDB as a service;
4. Select either:


- Run the service as Network Service user (default). This is a Windows user 
  account that is built-in to Windows;

- Run the service as a local or domain user;

  ![img.png](../Images/windows_mongodb.png)

- Service Name. Specify the service name. Default name is MongoDB. If you 
already have a service with the specified name, you must choose another name
- Data Directory. Specify the data directory, which corresponds to the 
  --dbpath. If the directory does not exist, the installer will create the directory and sets the directory access to the service user;
- Log Directory. Specify the Log directory, which corresponds to the 
  --logpath. If the directory does not exist, the installer will create the directory and sets the directory access to the service user.

5. Install MongoDB Compass (optional);
To have the wizard install MongoDB Compass, select Install MongoDB Compass (default);
6. When ready, click "Install".
7. To check is MongoDB server is installed, run:
```powershell
PS> mongod -h
```
Add the MongoDB server to the PATH environment variable if the following error appears:
```powershell
mongod : The term 'mongod' is not recognized as the name of a cmdlet, function, script file, or operable program.
```
By default, the server should have been installed in the folder `C:\Program Files\MongoDB\Server\{MONGODB_VERSION}\bin`


#### Install MongoSH from .msi

1. Open [MongoDB download center](https://www.mongodb.com/try/download/shell?jmp=docs);
2. In the Platform dropdown, select Windows 64-bit;
3. Click Download;
4. Double-click the installer file;
5. Follow the prompts to install `mongosh`;
6. To run mongo shell with cli use:
```powershell
PS> mongosh -h 
```

### Configuration

When your MongoDB server is up, you should configure it according to R8s
requirements:

- Connect to MongoDB server using `mongosh`:

  ```powershell
  $ mongosh --host 127.0.0.1 --port 27017
  Current Mongosh Log ID: 619cf3c96e43aa58d071920f
  Connecting to:          mongodb://127.0.0.1:27017/?directConnection=true
  ```
  Specify those host and port where exactly your server is running.


- Create a user with full rights to manage Rightsizer database. May db name be 
equal to `r8s`. Execute the following inside `mongosh`:

  ```mongosh
  > use admin
  switched to db admin
  > db.createUser({
      user: '{MONGO_USER_NAME}',
      pwd: '{MONGO_USER_PASSWORD}',
      roles: [
          { role: "dbOwner", db: "r8s"}
      ]
  });
  ```

- Export essential environment variables. Obviously, the user's credentials and 
database name are the same as used while creating a user:

  > ❗ After installing mongodb please provide next environment variables:
  ```powershell
  PS> setx MONGO_USER {MONGO_USER_NAME}
  PS> setx MONGO_PASSWORD {MONGO_USER_PASSWORD}
  PS> setx MONGO_URL 127.0.0.1:27017
  PS> setx MONGO_DATABASE r8s
  ```
  Set exactly those `MONGO_URL` and `MONGO_DATABASE` which you used.

> Next step: Install + configure Vault: [Windows](../Vault/Windows.md)
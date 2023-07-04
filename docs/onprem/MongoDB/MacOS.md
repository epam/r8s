## MongoDB Installation & Configuration on MacOS

### Installation
1. Install Xcode Command-Line Tools: 
   ```
   xcode-select --install
   ```

2. Tap the MongoDB Homebrew Tap to download the official Homebrew formula for 
   MongoDB and the Database Tools, by running the following command in 
   your macOS Terminal:
    ```
    brew tap mongodb/brew
    ```

3. To install MongoDB, run the following command in your macOS Terminal 
   application:
   ```
   brew install mongodb-community@5.0
   ```

4. To run MongoDB (i.e. the mongod process) as a macOS service, run:
   ```
   brew services start mongodb-community@5.0
   ```

### Configuration
Since your MongoDB server is up, you can start configuring it.

- Connect to MongoDB server using `mongosh`:

  ```bash
  $ mongosh --host 127.0.0.1 --port 27017
  Current Mongosh Log ID: 619cf3c96e43aa58d071920f
  Connecting to:          mongodb://127.0.0.1:27017/?directConnection=true
  ```
  Specify those host and port where exactly your server is running.


- Create a user with full rights to manage R8s database. Execute the 
  following command inside mongosh. 
  Note that DB name must be equal to r8s database name 
  (`r8s` by default). 

  ```mongosh
  > use admin
  switched to db admin
  > db.createUser({
      user: 'mongouser3',
      pwd: 'mongopassword',
      roles: [
          { role: "dbOwner", db: "r8s"}
      ]
  });
  ```

- Export essential environment variables. Obviously, the user's credentials and 
database name are the same as used while creating a user:

  ```bash
  $ export MONGO_DATABASE=r8s
  $ export MONGO_USER={MONGO_USER_NAME}
  $ export MONGO_PASSWORD={MONGO_USER_PASSWORD}
  $ export MONGO_URL=127.0.0.1:27017
  ```

> Next step: Install + configure Vault: [MacOS](../Vault/Macos.md)
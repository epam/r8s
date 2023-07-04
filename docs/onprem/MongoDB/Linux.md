## MongoDB Installation & Configuration on Linux

### Installation:

Follow the installation steps from the official [website](https://docs.mongodb.com/manual/administration/install-on-linux/)
according to your Linux distribution. Here are the sequence to install MongoDB
on Ubuntu Linux:

- Add MongoDB public GPG key:

  ```bash
  $ wget -qO - https://www.mongodb.org/static/pgp/server-5.0.asc | sudo apt-key add -
  ```
  *Note:* make sure you have `gnupg` package installed.


- Add the official MongoDB repository:

  ```bash
  $ echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu $(lsb_release -cs)/mongodb-org/5.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-5.0.list
  ```
  
- Update the list of available packages and install MongoDB:

  ```bash
  $ sudo apt-get update && sudo apt-get install mongodb-org
  ```

- Check whether MongoDB is installed:

  ```bash
  $ mongod -h  # primary server daemon
  ... 
  $ mongosh -h  # client shell
  ...
  ```
  
- Start MongoDB server:

  Using `systemd`:
  ```bash
  $ sudo systemctl start mongod
  ```
  Using `System V Init`:
  ```bash
  $ sudo service mongod start
  ```

### Configuration:

Since your MongoDB server is up, you can start configuring it.

- Connect to MongoDB server using `mongosh`:

  ```bash
  $ mongosh --host 127.0.0.1 --port 27017
  Current Mongosh Log ID: 619cf3c96e43aa58d071920f
  Connecting to:          mongodb://127.0.0.1:27017/?directConnection=true
  ```
  Specify those host and port where exactly your server is running.


- Create a user with full rights to manage r8s database. Execute the 
  following command inside mongosh. 
  Note that DB name must be equal to r8s database name 
  (`r8s` by default). 

  ```mongosh
  > use admin
  switched to db admin
  > db.createUser({
      user: 'mongouser1',
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

> Next step: Install + configure Vault: [Linux](../Vault/linux.md)
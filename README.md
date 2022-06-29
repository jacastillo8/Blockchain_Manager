# Blockchain Manager
This repository contains the source code to build and operate a Hyperledger Fabric blockchain in Ubuntu 18 and up. The manager uses a REST service to generate, interact and manage Hyperledger Fabric blockchains and its deployed smart contracts. The presented tool has the capability to also operate under ARM processors by utilizing most of the fabric containers developed by [chinyati](https://github.com/chinyati/Hyperledger-Fabric-ARM64-images).

## Getting Started
1. Download and install the programs below to run the fabric network.
    1. Git
    1. Docker & Docker Compose
    1. Go 1.15.x
    1. Python 3
        1. PyYAML
        1. Ruamel.yaml
        1. Docker
    1. NodeJS & NPM
1. After download, the folder structure should look similar to the directory structure shown below.
    ```bash
    Blockchain_Manager
    ├── blockchain_base
    │   ├── ...
    │   ├── chaincode
    │   │   ├── test_contract
    │   └── ...
    ├── express_app
    └── postman_collection_bcapi
    ```
1. Load collection `postman_collection_bcapi` into Postman.
1. Navigate to `express_app` folder and install node dependencies.
    ```bash
    cd express_app
    npm install
    ```
1. Navigate to `blockchain_base/bin` and check that binaries are executables.
    1. Otherwise run `sudo chmod +x *` inside the desired architecture (i.e., arm or vanilla) to update permissions to desired binaries
1. You are now ready to create your first blockchain.

### NPM commands to run
```bash
# To run REST Service
npm run mongoUp        # Generates MongoDB container to store blockchain structure information
npm start              # Starts Blockchain service on Port 4000
# Run Test Chain
npm run chainUp        # Generates a chain with 2 organizations, 1 peer per org, 1 orderer, 
                       # 1 channel (TestChannel) with 1 consortium of org1&2, and block
                       # structure of 1s (timeout), 10 (max messages) and 2MB (max bytes).
npm run contractUp     # Installs test_contract to TestChannel
npm run caliperUp      # Generates a caliper instance
# Remove all containers
npm run clean
```
### Use postman collection to interact with service
* Register a blockchain (`Register Blockchain`)
* Build registered blockchain (`Build Blockchain`)
* Insert new sample transaction to ledger (`Insert Transaction`)
* Query submitted transaction from ledger (`Evaluate Transaction`)

## Disclaimer
This tool is not intented to be deployed for production environments, instead it is tailored for research purposes to facilitate rapid blockchain prototyping and smart contract testing.
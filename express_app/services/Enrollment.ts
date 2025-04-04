'use strict'

import FabricCAServices from "fabric-ca-client";
import { Wallet } from "fabric-network";
import { Admin, Client } from "./utils/factories";
import { FabricConfigurationProfile } from "./utils/interfaces";

const { getCCP, getWallet, getMSP } = require('./utils/misc');
const logger = require('./utils/logger');

function getCA(organizationName: string, owner: string) {
    const ccp: FabricConfigurationProfile = getCCP(organizationName, owner);
    const caInfo = Object.values(ccp.certificateAuthorities)[0];
    const caTLSACerts = caInfo.tlsCACerts.pem;
    return new FabricCAServices(caInfo.url, { trustedRoots: caTLSACerts, verify: false }, caInfo.caName);;
}

function getAdminUser(wallet: Wallet, adminIdentity: any) {
    let provider = wallet.getProviderRegistry().getProvider(adminIdentity.type);    
    let admin = provider.getUserContext(adminIdentity, 'admin');
    return admin;
}

async function createNewAffiliation(ca: FabricCAServices, organizationName: string, organizationDepartment: string, registrar: any) {
    let affiliationService = ca.newAffiliationService();
    let registeredAffiliations = await affiliationService.getAll(registrar);

    let affiliations: any[] = []
    for (let i=0; i < registeredAffiliations.result.affiliations.length; i++) {
        affiliations = affiliations.concat(registeredAffiliations.result.affiliations[i].affiliations);
    }

    if (!affiliations.some(affiliation => { return affiliation.name === `${organizationName}.${organizationDepartment}`})) {
        let affiliation = `${organizationName}.${organizationDepartment}`;
        await affiliationService.create({
            name: affiliation,
            force: true
        }, registrar);
    }
}

export class Enrollment {
    async admin(user: Admin, owner: string) {
        const ca = getCA(user.org, owner);
        const wallet: Wallet = await getWallet(user.org, owner);
    
        if (!await wallet.get(user.enrollmentID)) {
            let enrollment = await ca.enroll({ enrollmentID: user.enrollmentID, enrollmentSecret: user.enrollmentSecret });
            
            let x509Identity = {
                credentials: {
                    certificate: enrollment.certificate,
                    privateKey: enrollment.key.toBytes()
                },
                mspId: getMSP(user.org),
                type: 'X.509'
            };
    
            await wallet.put(user.enrollmentID, x509Identity);
        } else {
            logger.error(`function: Enrollment.admin    error: Admin '${user.enrollmentID}' from ${user.org} already enrolled`);
        }
        return wallet.get(user.enrollmentID);
    }

    async client(user: Client, adminIdentity: any,  owner: string) {
        const ca = getCA(user.org, owner);
        const wallet: Wallet = await getWallet(user.org, owner);
    
        if (!await wallet.get(user.enrollmentID)) {
            let adminUser = await getAdminUser(wallet, adminIdentity);
            await createNewAffiliation(ca, user.org, user.department, adminUser);
    
            let secret = await ca.register({
                affiliation: `${user.org}.${user.department}`,
                enrollmentID: user.enrollmentID,
                role: 'client'
            }, adminUser);
    
            let enrollment = await ca.enroll({
                enrollmentID: user.enrollmentID,
                enrollmentSecret: secret
            });
    
            let x509Identity = {
                credentials: {
                    certificate: enrollment.certificate,
                    privateKey: enrollment.key.toBytes()
                },
                mspId: getMSP(user.org),
                type: 'X.509'
            };
    
            await wallet.put(user.enrollmentID, x509Identity);
        } else {
            logger.error(`function: Enrollment.client   error: Client '${user.enrollmentID}' from ${user.org} already enrolled`);
        }
    }
}

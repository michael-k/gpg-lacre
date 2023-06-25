# Lacre Project

Lacre is a fork and continuation of the original work on
[gpg-mailgate](https://github.com/TheGreatGooo/gpg-mailgate) project.  It is
still actively developed and should be considered as beta -- with all APIs and
internals being subject to change.  Please only use this software if you know
GnuPG well and accept occasional failures.

**Lacre** (wax seal in Portuguese) is a
[content filter](https://www.postfix.org/FILTER_README.html)
for Postfix that automatically encrypts incoming email using GnuPG for
recipients that have provided their public keys.

All incoming emails are automatically encrypted with users' public keys before
they are saved in the inbox.

# How it works

When Postfix receives a message, it "forwards" that message to Lacre.

Then, Lacre does the following:

1. If message already is encrypted, it just delivers the message immediately.
2. Checks the list of recipients, finds their public keys if any were
   provided.
3. Encrypts message if possible.
4. Delivers the message.

---

Work on this project in 2021 was funded by
[NGI Zero PET](https://nlnet.nl/thema/NGIZeroPET.html)
for which we are very thankful.

Made possible thanks to:<br>
![](https://nlnet.nl/logo/banner.png)

---

# Installation

For installation instructions, please refer to the included [INSTALL](INSTALL.md) file.

---

# Planned features

- Correctly displays attachments and general email content; currently will only display first part of multipart messages
- Public keys are stored in a dedicated gpg-home-directory
- Encrypts both matching incoming and outgoing mail (this means gpg-mailgate can be used to encrypt outgoing mail for software that doesn't support PGP or S/MIME)
- Easy installation
- People can submit their public key like to any keyserver to gpg-mailgate with the gpg-mailgate-web extension
- People can send an S/MIME signed email to register@yourdomain.tld to register their public key
- People can send their public OpenPGP key as attachment or inline to register@yourdomain.tld to register it

See also: [lacre-webgate](https://git.disroot.org/Lacre/lacre-webgate/) -- a
web interface allowing any user to upload PGP keys so that emails sent to them
from your mail server will be encrypted

This is forked from the original project at http://code.google.com/p/gpg-mailgate/

# Authors

This is a combined work of many developers and contributors.  We would like to
pay honours to original gpg mailbox developers for making this project happen,
and providing solid solution for encryption emails at rest:

* mcmaster <mcmaster@aphrodite.hurricanelabs.rsoc>
* Igor Rzegocki <ajgon@irgon.com> - [GitHub](https://github.com/ajgon/gpg-mailgate)
* Favyen Bastani <fbastani@perennate.com> - [GitHub](https://github.com/uakfdotb/gpg-mailgate)
* Colin Moller <colin@unixarmy.com> - [GitHub](https://github.com/LeftyBC/gpg-mailgate)
* Taylor Hornby <havoc@defuse.ca> - [GitHub](https://github.com/defuse/gpg-mailgate)
* Martin (uragit) <uragit@telemage.com> - [GitHub](https://github.com/uragit/gpg-mailgate)
* Braden Thomas - [BitBucket](https://bitbucket.org/drspringfield/emailencrypt.net/)
* Bruce Markey - [GitHub](https://github.com/TheEd1tor)
* Remko Tronçon - [GitHub](https://github.com/remko/phkp/)
* Kiritan Flux [GitHub](https://github.com/kflux)
* Fabian Krone [GitHub](https://github.com/fkrone/gpg-mailgate)

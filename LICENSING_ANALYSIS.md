# Reading a 1996 single-user CD-ROM license in a networked home

> **Context, not legal advice.** This page reads the recurring license language printed in the manuals for the recovered Provo Craft discs. It does not determine the license's enforceability, ownership of a particular copy, or anyone's legal rights. The original package terms and applicable law control.

## Why preserve this language?

The license is part of the historical record. It describes a late-1990s model in which clip art lived on one physical CD-ROM, a household commonly used one desktop computer, and local networks were comparatively unusual. Bulletin board systems (BBSs), online services, and early consumer internet access were already familiar ways to exchange files, while the Web was beginning to reach a much broader public than it had earlier in the decade.

The recovered discs are still governed by their original content terms. This repository therefore publishes recovery scripts and documentation only—not disc images, artwork, fonts, contact sheets, or other recovered output.

## The recurring restrictions

The manuals say that the designs and fonts are licensed rather than freely transferable. In plain language, the recurring terms say:

| Manual term | Practical effect described by the manual |
| --- | --- |
| **Single user** | Each purchased CD-ROM is assigned to one user. Giving it to friends, relatives, or coworkers is forbidden. |
| **Household use** | Personal or professional use is described as including members of the purchaser's household. |
| **Network installation** | Installation on any network is prohibited unless one CD-ROM has been purchased for every person who could access it at the same time. |
| **Internet distribution** | Transmission or distribution of the images over the internet, World Wide Web, or similar networks is described as a license violation. |
| **Commercial limits** | Limited professional use is described, while mass production, mass distribution, and commercial marketing of the images require permission. |

The exact wording matters. For example, the manuals describe a restriction on **installing the files on a network**; they do not expressly say that a standalone computer becomes noncompliant merely because it is connected to a home router.

## Why it feels unusually restrictive today

### 1996: a single-machine model

The license assumes a fairly simple workflow:

1. Insert a physical CD-ROM into one computer.
2. Install or open the files locally for one person.
3. Keep the files out of shared networks and avoid sending them to others.

That model could be followed by keeping the files on a single desktop drive and using the artwork locally.

### Today: ordinary computing is networked by default

A current household often has several computers, phones, tablets, a Wi-Fi router, shared printers, network-attached storage, cloud backup, synchronized folders, and household accounts. A strict reading of the network clause becomes awkward when ordinary conveniences can make a file accessible from more than one device or account.

Examples of modern situations that deserve caution under the manual's wording include:

- copying the artwork or fonts to a NAS, shared folder, or family server;
- placing the files in a sync service that makes them available across household devices;
- installing the files where multiple people may access the same network location; and
- sending artwork in email, chat, a web page, or social-media post.

The most striking phrase is the requirement for a CD-ROM for every person who could access a network installation **at the same time**. In a modern family home, that condition can be much broader than the number of people actively using the clip art. It treats potential simultaneous access—not actual creative use—as the relevant limit.

## The important distinction: connected is not necessarily shared

This analysis should not overread the license. A computer connected to Wi-Fi is not automatically the same thing as a network installation of the recovered files. The manuals target installation and access over a network.

But modern systems blur the boundary. Automatic backup, cloud synchronization, shared household storage, remote access, and collaboration tools can turn a local-looking folder into a network-accessible copy without much deliberate setup. That ambiguity is one reason this project keeps all recovered material in the Git-ignored `CD/` directory and keeps the public repository limited to tools and documentation.

## A deliberately limited public demonstration

This project considered publishing a small image that rendered each font's name in that font, along with a social-preview image showing some clip art in color or a contact-sheet-style selection of recovered artwork. The manuals' prohibition on internet transmission and distribution of the images is too restrictive for this project to treat those demonstrations as authorized merely because they would be small, recolored, cropped, presented in perspective, or otherwise derivative.

This is a conservative project decision, not a legal conclusion about every possible derivative use. The public social-preview illustration in this repository is newly created repository artwork; it does not contain recovered Provo Craft clip art, contact sheets, font files, or renderings made from the recovered fonts.

## What this repository does—and does not—claim

This project documents the manual language and adopts a conservative publishing boundary:

- Recovery scripts, dependency setup, tests, and historical documentation are published.
- Raw disc images, extracted clip art, converted PNG/SVG files, recovered font files, contact sheets, and font specimens remain local.
- References to third-party archival listings are historical pointers, not permissions to redistribute the material.
- No conclusion is made here about whether a particular private archive, backup, household setup, preview image, or publication would be permitted or enforceable.

For a decision with legal consequences, consult the original packaging and a qualified attorney in the relevant jurisdiction.

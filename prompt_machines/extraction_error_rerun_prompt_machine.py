import os
import json
import base64
import re
import argparse
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
from kortkat.prompt_data import PromptData, Content, TextPart, InlineDataPart

# 
# SCHEMA
# 

class PublicationType(str, Enum):
    MONOGRAPH = "monograph"
    MULTI_VOLUME = "multi-volume"
    PERIODICAL = "periodical"

class RelationType(str, Enum):
    BOUND_WITH = "bound-with"
    THEREWITH_BOUND = "therewith-bound"
    PRINTED_WITH = "printed-with"
    THEREWITH_PRINTED = "therewith-printed"
    CONTRIBUTION = "contribution"
    OFFPRINT = "offprint"
    FACSIMILE = "facsimile"
    CONTINUATION_OF = "continuation-of"
    CONTINUES_AS = "continues-as"

class SerialInfo(BaseModel):
    serial_title: str = Field(description="[Source: Zone 4 (Edition & Publication Stack)] The title of the serial.")
    volume_designation: Optional[str] = Field(description="[Source: Zone 4 (Edition & Publication Stack)] The enumeration of the volume, e.g. 'Vol. 1', 'T. 2', 'D. 3', 'Årg 1-3' or similar.")
    serial_classification: Optional[str] = Field(description="[Source: Zone 4 (Edition & Publication Stack)] The classification of the serial, telling where the serial is physically placed. A serial's classification is always handwritten and located adjacent, often below the serial title. Capture exactly what is stated, including parentheses, brackets and other characters.")

class Place(BaseModel):
    place_name: str = Field(description="The name of the place where the work was published or printed.")
    country_name: str = Field(description="ISO 3166 English name of the country where the place is located")
    country_code: str = Field(description="ISO 3166-1 alpha-2 code of the country where the place is located")

class Edition(BaseModel):
    edition_statement: Optional[str] = Field(description="[Source: Zone 4 (Edition & Publication Stack)] A specification of the edition (e.g. '3 uppl.', '3 edition' or similar).")
    volume_designation: Optional[str] = Field(description="[Source: Zone 4 (Edition & Publication Stack)] The enumeration of the volume, e.g. 'Vol. 1', 'T. 2', 'D. 3', 'Årg 1-3' or similar. For periodicals, this can also include a year.")
    format: Optional[str] = Field(description="[Source: Zone 4 (Edition & Publication Stack)] The physical format of the volume, e.g. '4:o', '8:o', '12:o', 'Fol'")
    place_of_publication: List[Place] = Field(description="[Source: Zone 4 (Edition & Publication Stack)] Where the work was published. If 'u.o.' is stated, there is no known place of publication.")
    place_of_printing: List[Place] = Field(description="[Source: Zone 4 (Edition & Publication Stack)] Where the work was printed. Place of printing is always indicated with the abbreviation 'tr.' before the place.")
    year_of_publication: Optional[int] = Field(ge=1000, description="[Source: Zone 4 (Edition & Publication Stack)] The single integer year of publication or printing. If a date span or multiple years are present (e.g., '1924-1925' or '1850, 1852'), extract ONLY the earliest year as the integer (e.g., 1924). If 'u.å.' is stated, output null.")
    year_of_publication_exact_string: Optional[str] = Field(description="[Source: Zone 4 (Edition & Publication Stack)] When the work was published or printed. If 'u.å.' is stated, there is no known year. Capture EXACTLY what is stated.")
    year_of_publication_compact_string: Optional[str] = Field(description="""[Source: Zone 4 (Edition & Publication Stack)] A compact string representing the year or years of publication, following a specific grammar. The output MUST strictly adhere to these rules:
            **Single Year:** Use a four-digit format 'YYYY'. Example: '1984'.
            **Multiple Items:** Use a comma ',' without spaces to separate distinct years or ranges. Example: '1984,1992'.
            **Closed Range:** For a continuous range of years, use a hyphen '-' between the start and end year. Example: '1990-1995'.
            **Open Range:** For an ongoing publication, use the start year followed by a hyphen. Example: '2010-'.
            **Combinations:** Combine these rules for complex cases. For a card listing years 1850, 1852, the period from 1901 to 1910, and an ongoing series started in 1925, the correct output is '1850,1852,1901-1910,1925-'."""
    )
    serial_references: List[SerialInfo] = Field(description="[Source: Zone 4 (Edition & Publication Stack)] List of serials the edition is part of. A reference to a serial can be indicated in several different ways: prefixed with an equal sign (“=”), enclosed in slashes (“/”) or parentheses. Sometimes there is no specific indication except for the title of the serial. Information on volume etc can also be included in the reference. The reference to the serial is written below each edition.")

class RelatedWork(BaseModel):
    relation_type: RelationType = Field(description="""[Source: Zone 5 (Secondary Notes & Relations Zone)] The type of relation. The relation types are defined as follows:
            **Category: bound-with** You must classify the reference as 'bound-with' ONLY IF you literally see the exact Swedish strings "Sammanbunden med:", "Sammanb. med:", or "Smb. med:" printed on the card. CRITICAL CONSTRAINTS: Do NOT classify based on semantic meaning or the general concept of books being bound together. Do NOT accept "similar" phrases, synonyms, or translated text. For example, if you see English phrases like "Bound with", French phrases like "Relié avec", or German phrases like "Angebunden", you must NOT classify it as 'bound-with'. You are restricted strictly to the three Swedish string variations provided.
            **Category: therewith-bound** You must classify the reference as 'therewith-bound' ONLY IF you literally see one of the exact Swedish strings "Därm. smb.", "Därmed smb.", "Därmed sammanbunden", "Därmed sammanb.", or "Därm. sammanb." printed on the card. CRITICAL CONSTRAINTS: Do NOT classify based on semantic meaning or the general concept of books being bound together. Do NOT accept "similar" phrases, synonyms, or translated text. For example, if you see English phrases like "Bound therewith", French phrases like "Relié à la suite", or German phrases like "Daran gebunden", you must NOT classify it as 'therewith-bound'. You are restricted strictly to the exact Swedish string variations provided above.
            **Category: printed-with** You must classify the reference as 'printed-with' ONLY IF you literally see the exact Swedish strings "Smtr. med:", "Sammantryckt med:", or "Sammantr. med:" printed on the card. CRITICAL CONSTRAINTS: Do NOT classify based on semantic meaning or the general concept of works being printed together. Do NOT accept "similar" phrases, synonyms, or translated text. For example, if you see English phrases like "Printed with", French phrases like "Imprimé avec", or German phrases like "Zusammengedruckt mit", you must NOT classify it as 'printed-with'. You are restricted strictly to the three Swedish string variations provided.
            **Category: therewith-printed** You must classify the reference as 'therewith-printed' ONLY IF you literally see one of the exact Swedish strings "Därmed smtr.:", "Därm. Smtr.:", "Därmed sammantryckt:", "Därm. Sammantryckt:", or "Därm. sammantr.:" printed on the card. CRITICAL CONSTRAINTS: Do NOT classify based on semantic meaning or the general concept of works being printed together. Do NOT accept "similar" phrases, synonyms, or translated text. For example, if you see English phrases like "Printed therewith", French phrases like "Imprimé à la suite", or German phrases like "Mitgedruckt", you must NOT classify it as 'therewith-printed'. You are restricted strictly to the exact Swedish string variations provided above.
            **Category: contribution** You must classify the reference as 'contribution' ONLY IF you literally see the exact Swedish string "i:" (or "I:") printed on the card. CRITICAL CONSTRAINTS: Do NOT classify based on semantic meaning or the general concept of a work being a part of another work (such as an article or a chapter). Do NOT accept synonyms or translated text. For example, if you see the English or German "In:", the French "Dans:", or the Spanish "En:", you must NOT classify it as a 'contribution'. You are restricted strictly to the exact literal Swedish string provided.
            **Category: offprint** Use 'offprint' ONLY IF you literally see the exact Swedish strings "Ur:" or "Särtryck ur" before the referenced title. Do NOT translate the strings, if you see French phrases like "Extrait du", English phrases like "Reprinted from", or German phrases like "Sonderabdruck", you must NOT classify it as an 'offprint'. If the exact literal Swedish strings "Ur:" or "Särtryck ur" are missing, it is not an offprint.
            **Category: facsimile** You must classify the reference as 'facsimile' ONLY IF you literally see the exact Swedish strings "Faksimil" or "Faksimilupplaga" printed on the card. CRITICAL CONSTRAINTS: Do NOT classify based on semantic meaning or the general concept of the work being a reproduction or exact copy. Do NOT accept "similar" words, synonyms, or translated text. For example, if you see the English word "Facsimile", the French word "Fac-similé", or the German word "Faksimile-Ausgabe", you must NOT classify it as 'facsimile'. You are restricted strictly to the exact Swedish string variations provided above.
            **Category: continuation-of** You must classify the reference as 'continuation-of' ONLY IF you literally see one of the exact Swedish strings "Forts. av", "Forts. på", "Fortsättning av", or "Fortsättning på" printed on the card preceding the related title. CRITICAL CONSTRAINTS: Do NOT classify based on semantic meaning or the general concept of a work continuing another work. Do NOT accept "similar" phrases, synonyms, or translated text. For example, if you see English phrases like "Continuation of", French phrases like "Suite de", or German phrases like "Fortsetzung von", you must NOT classify it as 'continuation-of'. You are restricted strictly to the exact Swedish string variations provided above.
            **Category: continues-as** You must classify the reference as 'continues-as' ONLY IF you literally see the exact Swedish string "Forts. se:" printed on the card preceding the related title. CRITICAL CONSTRAINTS: Do NOT classify based on semantic meaning or the general concept of a work being continued by another work. Do NOT accept synonyms or translated text. For example, if you see English phrases like "Continued by", French phrases like "Devenu", or German phrases like "Fortgesetzt als", you must NOT classify it as 'continues-as'. You are restricted strictly to the exact Swedish string."""
    )
    related_author: Optional[str] = Field(description="[Source: Zone 5 (Secondary Notes & Relations Zone)] The author of the related work.")
    related_title: Optional[str] = Field(description="[Source: Zone 5 (Secondary Notes & Relations Zone)] The title of the related work.")
    related_place_of_publication: Optional[str] = Field(description="[Source: Zone 5 (Secondary Notes & Relations Zone)] The place of publication of the related work.")
    related_format: Optional[str] = Field(description="[Source: Zone 5 (Secondary Notes & Relations Zone)] The format of the related work.")
    related_year: Optional[str] = Field(description="[Source: Zone 5 (Secondary Notes & Relations Zone)] The year of publication of the related work.")
    related_edition: Optional[str] = Field(description="[Source: Zone 5 (Secondary Notes & Relations Zone)] The edition of the related work.")

class Title(BaseModel):
    title: str = Field(description="[Source: Zone 2 (Top Header Block (Main Entry)) & Zone 3 (Title Block)] Extract the Title Proper for MARC Field 245 $a. This is the primary name of the work on the card. Instruction: Extract the main title exactly as it appears. In older cards, the title often ends where a descriptive phrase (like 'a novel') or an author's name begins. If there is no punctuation like a colon or slash to mark the end, stop extraction once the text shifts to describing the work or naming a person.")
    remainder_of_title: Optional[str] = Field(description="[Source: Zone 3 (Title Block)] Identify the Remainder of Title for MARC Field 245 $b. This includes subtitles or alternative titles. Instruction: Look for descriptive phrases that explain the title (e.g., 'a story of the sea' or 'being a history of...').")
    statement_of_responsibility: Optional[str] = Field(description="[Source: Zone 3 (Title Block)] Identify the Statement of Responsibility for MARC Field 245 $c. Look for the names of authors, editors, or translators. Instruction: Look for keywords like 'by,' 'compiled by,' or names appearing after the title/subtitle. Transcription Rule: Keep names in the order they appear (e.g., 'by William Shakespeare').")

class Role(BaseModel):
    code: str = Field(description="""The role of the person or organisation as defined in the MARC Code List for Relators. Output the code of the role. The role MUST be one of the following roles:
            Term: abridger, Code: abr, Definition: Shortens or condenses the original work without changing its nature.
            Term: actor, Code: act, Definition: A performer contributing to a work by acting as a cast member.
            Term: adapter, Code: adp, Definition: Modifies content for a different medium or audience (e.g.,  novel to film).
            Term: addressee, Code: rcp, Definition: The person or organization to whom correspondence is addressed.
            Term: analyst, Code: anl, Definition: Reviews,  examines,  and interprets data in a specific area.
            Term: animator, Code: anm, Definition: Gives apparent movement to inanimate objects or drawings.
            Term: annotator, Code: ann, Definition: Makes manuscript annotations on an item.
            Term: announcer, Code: anc, Definition: Makes announcements on TV/radio to identify stations or introduce shows.
            Term: appellant, Code: apl, Definition: Appeals a lower court's decision.
            Term: appellee, Code: ape, Definition: The party against whom an appeal is taken.
            Term: applicant, Code: app, Definition: Responsible for the submission of an application.
            Term: architect, Code: arc, Definition: Responsible for creating an architectural design.
            Term: arranger, Code: arr, Definition: Rewrites a musical composition for a different medium of performance.
            Term: art copyist, Code: acp, Definition: Makes copies of works of visual art.
            Term: art director, Code: adi, Definition: Oversees artists/craftspeople building sets for motion pictures/TV.
            Term: artist, Code: art, Definition: Creates a work by conceiving/implementing an original graphic design.
            Term: artistic director, Code: ard, Definition: Controls the development of the artistic style of an entire production.
            Term: assignee, Code: asg, Definition: A person/organization to whom a license has been transferred.
            Term: associated name, Code: asn, Definition: Associated with an item where specific provenance is unclear.
            Term: attributed name, Code: att, Definition: A name to which authorship is attributed by some authority.
            Term: auctioneer, Code: auc, Definition: In charge of the public auctioning of goods.
            Term: audio engineer, Code: aue, Definition: Manages technical sound aspects during recording and mixing.
            Term: audio producer, Code: aup, Definition: Responsible for business aspects of an audio recording.
            Term: author, Code: aut, Definition: Responsible for creating a primarily textual work.
            Term: author in quotations..., Code: aqt, Definition: A person whose work is largely quoted in a resource they didn't write.
            Term: author of dialog, Code: aud, Definition: Responsible for the dialog or spoken commentary.
            Term: autographer, Code: ato, Definition: A person whose manuscript signature appears on an item.
            Term: bibliographic antecedent, Code: ant, Definition: Responsible for a resource upon which the current resource is based.
            Term: binder, Code: bnd, Definition: A person who binds an item.
            Term: binding designer, Code: bdd, Definition: Responsible for the binding design of a book.
            Term: blurb writer, Code: blw, Definition: Writes a commendation for a work appearing on the publication.
            Term: book artist, Code: bka, Definition: Exploits the book form or alters its physical structure as art.
            Term: book designer, Code: bkd, Definition: Responsible for the entire graphic design of a book.
            Term: book producer, Code: bkp, Definition: Responsible for the production of books and other print media.
            Term: bookjacket designer, Code: bjd, Definition: Responsible for the design of flexible covers (dust jackets).
            Term: bookplate designer, Code: bpd, Definition: Responsible for the design of an owner's identification label.
            Term: bookseller, Code: bsl, Definition: Makes bibliographic materials available for purchase.
            Term: braille embosser, Code: brl, Definition: Involved in manufacturing a resource by embossing Braille cells.
            Term: broadcaster, Code: brd, Definition: Involved in broadcasting a resource via radio,  TV,  or webcast.
            Term: calligrapher, Code: cll, Definition: Writes in an artistic hand.
            Term: camera operator, Code: cop, Definition: Operates a motion picture camera.
            Term: cartographer, Code: ctg, Definition: Responsible for creating a map,  atlas,  or globe.
            Term: caster, Code: cas, Definition: Manufactures a resource by pouring liquid into a mold.
            Term: casting director, Code: cad, Definition: Assigns roles and duties to performers.
            Term: censor, Code: cns, Definition: Examines resources to suppress objectionable parts.
            Term: choreographer, Code: chr, Definition: Creates or contributes to a work of movement/dance.
            Term: cinematographer, Code: cng, Definition: In charge of photographing a motion picture (director of photography).
            Term: client, Code: cli, Definition: The person/organization for whom another is acting.
            Term: collection registrar, Code: cor, Definition: Lists or inventories items in a collection.
            Term: collector, Code: col, Definition: Brings together items from various sources to form a collection.
            Term: collotyper, Code: clt, Definition: Manufactures prints using the collotype process.
            Term: colorist, Code: clr, Definition: Applies color to drawings,  prints,  or moving images.
            Term: commentator, Code: cmm, Definition: Provides discussion/analysis on a recording or film.
            Term: commentator for text, Code: cwt, Definition: Writes commentary or explanatory notes about a text.
            Term: compiler, Code: com, Definition: Creates a new work by selecting and arranging data/information.
            Term: complainant, Code: cpl, Definition: Applies to the courts for redress.
            Term: complainant-appellant, Code: cpt, Definition: A complainant who takes an appeal to a higher court.
            Term: complainant-appellee, Code: cpe, Definition: A complainant against whom an appeal is taken.
            Term: composer, Code: cmp, Definition: Creates or contributes to a musical resource.
            Term: compositor, Code: cmt, Definition: Creates the metal slugs or molds used for printing text (typesetter).
            Term: conceptor, Code: ccp, Definition: Responsible for the original idea on which a work is based.
            Term: conductor, Code: cnd, Definition: Leads a performing group (orchestra,  chorus,  etc.).
            Term: conservator, Code: con, Definition: Preserves or treats printed/manuscript material.
            Term: consultant, Code: csl, Definition: Provides professional advice in a specialized field.
            Term: consultant to a project, Code: csp, Definition: Provides intellectual overview for a specific task.
            Term: contestant, Code: cos, Definition: Opposes or disputes a claim in a court of law.
            Term: contestant-appellant, Code: cot, Definition: A contestant taking an appeal to reverse a judgment.
            Term: contestant-appellee, Code: coe, Definition: A contestant against whom an appeal is taken.
            Term: contestee, Code: cts, Definition: Defends a claim being disputed in a court of law.
            Term: contestee-appellant, Code: ctt, Definition: A contestee taking an appeal to reverse a judgment.
            Term: contestee-appellee, Code: cte, Definition: A contestee against whom an appeal is taken.
            Term: contractor, Code: ctr, Definition: Enters into a contract to perform a specific task.
            Term: contributor, Code: ctb, Definition: Responsible for making contributions to the resource.
            Term: copyright claimant, Code: cpc, Definition: Listed as copyright owner at the time of registration.
            Term: copyright holder, Code: cph, Definition: To whom legal rights have been granted or transferred.
            Term: corrector, Code: crr, Definition: Corrects manuscripts or proofs (scriptorium official).
            Term: correspondent, Code: crp, Definition: The writer or recipient of a letter or communication.
            Term: costume designer, Code: cst, Definition: Designs costumes for a production.
            Term: court governed, Code: cou, Definition: A court governed by specific court rules.
            Term: court reporter, Code: crt, Definition: Prepares a court's opinions for publication.
            Term: cover designer, Code: cov, Definition: Graphic design of a book cover or slipcase.
            Term: creator, Code: cre, Definition: Responsible for the intellectual or artistic content.
            Term: curator, Code: cur, Definition: Conceives and organizes an exhibition or collection.
            Term: dancer, Code: dnc, Definition: A performer who dances in a presentation.
            Term: data contributor, Code: dtc, Definition: Submits data for inclusion in a database.
            Term: data manager, Code: dtm, Definition: Responsible for managing databases or data sources.
            Term: dedicatee, Code: dte, Definition: The person to whom a resource is dedicated.
            Term: dedicator, Code: dto, Definition: Writes a dedication statement or verse.
            Term: defendant, Code: dfd, Definition: The party accused in a criminal or civil proceeding.
            Term: defendant-appellant, Code: dft, Definition: A defendant who appeals a judgment.
            Term: defendant-appellee, Code: dfe, Definition: A defendant against whom an appeal is taken.
            Term: degree committee..., Code: dgc, Definition: Member of a committee considering an academic thesis.
            Term: degree granting..., Code: dgg, Definition: The organization granting an academic degree.
            Term: degree supervisor, Code: dgs, Definition: Oversees a higher-level academic degree.
            Term: delineator, Code: dln, Definition: Executes technical drawings from others' designs.
            Term: depicted, Code: dpc, Definition: An entity portrayed in a work of art.
            Term: depositor, Code: dpt, Definition: Current owner who deposits an item into others' custody.
            Term: designer, Code: dsr, Definition: Responsible for creating a design for an object.
            Term: director, Code: drt, Definition: Manages and supervises a performance or program.
            Term: dissertant, Code: dis, Definition: Presents a thesis for a university degree.
            Term: distribution place, Code: dbp, Definition: The place from which a resource is distributed.
            Term: distributor, Code: dst, Definition: Has marketing rights for a resource.
            Term: dj, Code: djo, Definition: Mixes tracks during a live performance or session.
            Term: donor, Code: dnr, Definition: Former owner who donated the item.
            Term: draftsman, Code: drm, Definition: Makes detailed plans for buildings,  machines,  etc.
            Term: dubbing director, Code: dbd, Definition: Supervises adding new dialog to a soundtrack.
            Term: dubious author, Code: dub, Definition: A person to whom authorship has been incorrectly ascribed.
            Term: editor, Code: edt, Definition: Revises or elucidates content for publication.
            Term: editor of compilation, Code: edc, Definition: Selects and puts together works by various creators.
            Term: editor of moving image, Code: edm, Definition: Assembles and trims film or video formats.
            Term: editorial director, Code: edd, Definition: Legal/intellectual responsibility for a serial or multipart work.
            Term: electrician, Code: elg, Definition: Sets up and focuses lighting rigs for a production.
            Term: electrotyper, Code: elt, Definition: Creates duplicate printing surfaces via electrodepositing.
            Term: enacting jurisdiction, Code: enj, Definition: Jurisdiction enacting a law or constitution.
            Term: engineer, Code: eng, Definition: Responsible for technical planning and design (construction).
            Term: engraver, Code: egr, Definition: Cuts letters/figures onto a printing surface.
            Term: etcher, Code: etr, Definition: Produces text/images via acid corrosion on a surface.
            Term: event place, Code: evp, Definition: Place where a conference or concert took place.
            Term: expert, Code: exp, Definition: In charge of description/appraisal of goods (rare items).
            Term: facsimilist, Code: fac, Definition: Executes a facsimile of a resource.
            Term: field director, Code: fld, Definition: Supervises work to collect raw data in a real setting.
            Term: film director, Code: fmd, Definition: Director of a filmed performance.
            Term: film distributor, Code: fds, Definition: Distributes moving images to theaters.
            Term: film editor, Code: flm, Definition: Assembles filmed material and controls synchronization.
            Term: film producer, Code: fmp, Definition: Business aspects of a film production.
            Term: filmmaker, Code: fmk, Definition: Individually responsible for all aspects of an independent film.
            Term: first party, Code: fpy, Definition: Identified as the party of the first part in a contract.
            Term: forger, Code: frg, Definition: Imitates something of value with intent to defraud.
            Term: former owner, Code: fmo, Definition: Person/family formerly having legal possession.
            Term: honoree, Code: hon, Definition: Person/organization in whose honor a resource is issued.
            Term: host, Code: hst, Definition: Leads a program (broadcast) with guests and performers.
            Term: host institution, Code: his, Definition: The organization hosting an event or providing facilities.
            Term: illustrator, Code: ill, Definition: Supplements primary content with drawings/diagrams.
            Term: illuminating engineer, Code: ileg, Definition: Designs/supervises lighting for a production.
            Term: illuminator, Code: ilu, Definition: Decoration/illustration of manuscripts with colors/gold.
            Term: inscriber, Code: ins, Definition: Adds a handwritten dedication (not the creator).
            Term: instrumentalist, Code: itr, Definition: A performer contributing by playing a musical instrument.
            Term: interviewee, Code: ive, Definition: Responds to questions during an interview.
            Term: interviewer, Code: ivr, Definition: Acts as the interviewer for a resource.
            Term: inventor, Code: inv, Definition: Creates a new device or process.
            Term: issuing body, Code: isb, Definition: The organization issuing the work.
            Term: judge, Code: jud, Definition: Hears and decides on legal matters in court.
            Term: jurisdiction governed, Code: jug, Definition: Jurisdiction governed by a law enacted by another.
            Term: laboratory, Code: lbr, Definition: Provides scientific analyses of material samples.
            Term: laboratory director, Code: ldr, Definition: Manages work done in a controlled lab setting.
            Term: landscape architect, Code: lsa, Definition: Creates landscape works/land features.
            Term: lead, Code: led, Definition: Takes primary responsibility for an activity.
            Term: lender, Code: len, Definition: Permits temporary use of an item (e.g.,  for microfilming).
            Term: letterer, Code: ltr, Definition: Draws text/sound effects for comics/graphic novels.
            Term: libelant, Code: lil, Definition: Files a libel in an ecclesiastical or admiralty case.
            Term: libelant-appellant, Code: lit, Definition: A libelant taking an appeal to reverse a judgment.
            Term: libelant-appellee, Code: lie, Definition: A libelant against whom an appeal is taken.
            Term: libelee, Code: lel, Definition: Party against whom a libel has been filed.
            Term: libelee-appellant, Code: let, Definition: A libelee taking an appeal to reverse a judgment.
            Term: libelee-appellee, Code: lee, Definition: A libelee against whom an appeal is taken.
            Term: librettist, Code: lbt, Definition: Author of a libretto for an opera or stage work.
            Term: licensee, Code: lse, Definition: Recipient of the right to print or publish.
            Term: licensor, Code: lso, Definition: Grants a license to print or publish.
            Term: lighting designer, Code: lgd, Definition: Designs the lighting scheme for a production.
            Term: lithographer, Code: ltg, Definition: Prepares a stone/plate for printing via lithography.
            Term: lyricist, Code: lyr, Definition: Author of the words of a song.
            Term: manufacture place, Code: mfp, Definition: Place where a resource was manufactured.
            Term: manufacturer, Code: mfr, Definition: Responsible for the manufacturing of a manifestation.
            Term: markup editor, Code: mrk, Definition: Prepares a work for publication via markup (HTML,  XML).
            Term: metadata contact, Code: mdc, Definition: Compiles/maintains descriptions of metadata sets.
            Term: metal-engraver, Code: mte, Definition: Cuts decorations/letters on a metal surface for printing.
            Term: minute taker, Code: mtk, Definition: Records the minutes of a meeting.
            Term: mixing engineer, Code: mxe, Definition: Manipulates and mixes audio tracks.
            Term: moderator, Code: mod, Definition: Leads a program where topics are discussed.
            Term: monitor, Code: mon, Definition: Supervises contract compliance and report distribution.
            Term: music copyist, Code: mcp, Definition: Transcribes or copies musical notation.
            Term: music programmer, Code: mup, Definition: Uses electronic devices/software to generate sounds.
            Term: musical director, Code: msd, Definition: Coordinates composer,  sound editor,  and mixers.
            Term: musician, Code: mus, Definition: Performs music (general term when role is unspecified).
            Term: narrator, Code: nrt, Definition: Reads or speaks to give an account of events.
            Term: news anchor, Code: nan, Definition: Overall control of a news television program.
            Term: onscreen participant, Code: onp, Definition: Takes an active role in a nonfiction moving image work.
            Term: onscreen presenter, Code: osp, Definition: Appears on screen to provide contextual information.
            Term: opponent, Code: opn, Definition: Responsible for opposing a thesis in an academic disputation.
            Term: organizer, Code: orm, Definition: Responsible for organizing a conference/event.
            Term: origin place, Code: orp, Definition: Place from which a resource originated.
            Term: originator, Code: org, Definition: The organization from which a resource originated.
            Term: other, Code: oth, Definition: Role not otherwise identified on the list.
            Term: owner, Code: own, Definition: The current legal owner of an item.
            Term: panelist, Code: pan, Definition: Member of a panel that provides discussion.
            Term: papermaker, Code: ppm, Definition: Involved in manufacturing the paper for a resource.
            Term: patent holder, Code: pth, Definition: To whom a patent for an invention has been granted.
            Term: patron, Code: pat, Definition: Commissions and pays for a work.
            Term: penciller, Code: pnc, Definition: Produces initial line drawings for comics/animation.
            Term: performer, Code: prf, Definition: General term for music/acting/dance/speech contributors.
            Term: permitting agency, Code: pma, Definition: Agency that issues permits for work to be done.
            Term: photographer, Code: pht, Definition: Responsible for creating a photographic work.
            Term: place of address, Code: pad, Definition: Place to which a resource (letter) is sent.
            Term: plaintiff, Code: ptf, Definition: Party who brings a suit in a civil proceeding.
            Term: plaintiff-appellant, Code: ptt, Definition: A plaintiff taking an appeal to reverse a judgment.
            Term: plaintiff-appellee, Code: pte, Definition: A plaintiff against whom an appeal is taken.
            Term: platemaker, Code: plt, Definition: Prepares plates for printed images or text.
            Term: praeses, Code: pra, Definition: Faculty moderator of an academic disputation.
            Term: presenter, Code: pre, Definition: Associated with production/finance/distribution (X presents).
            Term: printer, Code: prt, Definition: Involved in manufacturing text/music from type/plates.
            Term: printer of plates, Code: pop, Definition: Specifically prints illustrations from plates.
            Term: printmaker, Code: prm, Definition: Makes a relief/intaglio/planographic printing surface.
            Term: process contact, Code: prc, Definition: Responsible for performing/initiating a process.
            Term: producer, Code: pro, Definition: Business aspects of a production (fundraising,  hiring).
            Term: production company, Code: prn, Definition: Management organization for a production.
            Term: production designer, Code: prs, Definition: Designs overall visual appearance of a moving image.
            Term: production manager, Code: pmn, Definition: Responsible for technical/business matters in a production.
            Term: production personnel, Code: prd, Definition: Props,  lighting,  and effects workers for a production.
            Term: programmer, Code: prg, Definition: Writes computer software.
            Term: proofreader, Code: pfr, Definition: Corrects proofs for publication.
            Term: property owner, Code: pown, Definition: Current owner of real property.
            Term: publisher, Code: pbl, Definition: Makes a resource available to the public.
            Term: publishing director, Code: pbd, Definition: Intellectual/legal responsibility for a publishing house.
            Term: puppeteer, Code: ppt, Definition: Manipulates puppets in a theatrical presentation.
            Term: radio director, Code: rdd, Definition: Supervises a radio program.
            Term: radio producer, Code: rpc, Definition: Business aspects of a radio program.
            Term: rapporteur, Code: rap, Definition: Reports on the proceedings of an organization's meetings.
            Term: recording engineer, Code: rce, Definition: Supervises technical aspects of a recording session.
            Term: recordist, Code: rcd, Definition: Captures sounds/video during a recording session.
            Term: redaktor, Code: red, Definition: Writes/develops the framework without content responsibility.
            Term: remix artist, Code: rxa, Definition: Recombines and mixes previously-recorded sounds.
            Term: renderer, Code: ren, Definition: Prepares drawings of architectural designs in perspective.
            Term: reporter, Code: rpt, Definition: Writes or presents news reports.
            Term: repository, Code: rps, Definition: Hosts data/objects and provides long-term shared access.
            Term: research team head, Code: rth, Definition: Directed or managed a research project.
            Term: research team member, Code: rtm, Definition: Participated in a research project without managing it.
            Term: researcher, Code: res, Definition: Responsible for performing research.
            Term: respondent, Code: rsp, Definition: Answers courts or defends a thesis in disputation.
            Term: respondent-appellant, Code: rst, Definition: A respondent taking an appeal to reverse a judgment.
            Term: respondent-appellee, Code: rse, Definition: A respondent against whom an appeal is taken.
            Term: responsible party, Code: rpy, Definition: Legally responsible for the published material.
            Term: restager, Code: rsg, Definition: Restages a choreographic/dramatic work (minimal new content).
            Term: restorationist, Code: rsr, Definition: Technical/editorial procedures to repair degradation.
            Term: reviewer, Code: rev, Definition: Responsible for the review of a book/film/performance.
            Term: rubricator, Code: rbr, Definition: Responsible for distinctive color headings/parts in a manuscript.
            Term: scenarist, Code: sce, Definition: Author of a screenplay (generally silent era scenarios).
            Term: scientific advisor, Code: sad, Definition: Provides scientific/historical competence to a work.
            Term: screenwriter, Code: aus, Definition: Author of a screenplay,  script,  or scene.
            Term: scribe, Code: scr, Definition: Amanuensis or writer of manuscripts.
            Term: sculptor, Code: scl, Definition: Creates three-dimensional works via carving/modeling.
            Term: second party, Code: spy, Definition: Identified as the party of the second part in a contract.
            Term: secretary, Code: sec, Definition: Expresses the views of an organization.
            Term: seller, Code: sll, Definition: Former owner who sold the item.
            Term: set designer, Code: std, Definition: Translates sketches into architectural structures for a stage.
            Term: setting, Code: stg, Definition: Entity in which the plot of a work takes place.
            Term: signer, Code: sgn, Definition: Signature appears without provenance statement.
            Term: singer, Code: sng, Definition: Uses voice to produce music (vocalist).
            Term: software developer, Code: swd, Definition: Researches,  designs,  and tests software.
            Term: sound designer, Code: sds, Definition: Produces sound score and mic installations.
            Term: sound engineer, Code: sde, Definition: Records sound on set during filmmaking.
            Term: speaker, Code: spk, Definition: Contributes by speaking words (lecture,  speech).
            Term: special effects..., Code: sfx, Definition: Creates on-set mechanical or in-camera effects.
            Term: sponsor, Code: spn, Definition: Sponsoring research or an event.
            Term: stage director, Code: sgd, Definition: Management and supervision of a performance.
            Term: stage manager, Code: stm, Definition: In charge of stage crews and assistant to the director.
            Term: standards body, Code: stn, Definition: Responsible for the development of a standard.
            Term: stereotyper, Code: str, Definition: Creates new plates by molding other printing surfaces.
            Term: storyteller, Code: stl, Definition: Relays a story with dramatic interpretation.
            Term: supporting host, Code: sht, Definition: Allocates facilities or resources to support an event.
            Term: surveyor, Code: srv, Definition: Provides measurements for a geographic area.
            Term: teacher, Code: tch, Definition: Gives instruction or provides a demonstration.
            Term: technical advisor, Code: tad, Definition: Advises on authentic portrayal of a subject.
            Term: technical director, Code: tcd, Definition: In charge of scenery,  props,  and lights.
            Term: television director, Code: tld, Definition: Supervision of a television program.
            Term: television guest, Code: tlg, Definition: Appears in a television program (talk/variety show).
            Term: television host, Code: tlh, Definition: Leads a television program with guests.
            Term: television producer, Code: tlp, Definition: Business aspects of a television program.
            Term: television writer, Code: tau, Definition: Writes scripts for a television series/episode.
            Term: thesis advisor, Code: ths, Definition: Supervises a candidate's development of a thesis.
            Term: transcriber, Code: trc, Definition: Prepares a copy of a work in another notation.
            Term: translator, Code: trl, Definition: Expresses a work in another language.
            Term: type designer, Code: tyd, Definition: Designs the characters for a font/typeface.
            Term: unidentified, Code: udf, Definition: Relationship to the work is unknown.
            Term: videographer, Code: vdg, Definition: Records images/sound on video formats.
            Term: wood-engraver, Code: wde, Definition: Cuts designs into wood blocks (end-grain) for printing.
            Term: woodcutter, Code: wdc, Definition: Cuts designs into wood blocks (side-grain) for printing.
            Term: writer of lyrics, Code: wal, Definition: Writes words added to an expression of a musical work.
            Term: writer of added text, Code: wat, Definition: Provides text for a non-textual work (captions/maps).
            Term: writer of afterword, Code: waw, Definition: Provides an afterword to the original work.
            Term: writer of film story, Code: wfs, Definition: Writes an original story expressly for a motion picture.
            Term: writer of foreword, Code: wfw, Definition: Provides a foreword to the original work.
            Term: writer of intertitles, Code: wft, Definition: Writes dialogue/expository intertitles for silent films.
            Term: writer of introduction, Code: win, Definition: Provides an introduction to the original work.
            Term: writer of preface, Code: wpr, Definition: Provides a preface to the original work.
            Term: writer of content, Code: wst, Definition: Provides supplementary textual content to a work.
            Term: writer of TV story, Code: wts, Definition: Writes an original story expressly for a TV program."""
    )

class Person(BaseModel):
    name: str = Field(description="The full name of the author. Output the name in the form of 'Lastname, Firstname' if both are available. Remove any brackets but keep the content within.")
    role: Role = Field(description="The role of the person as defined in the MARC Code List for Relators. Output the code of the role.")

class Organisation(BaseModel):
    name: str = Field(description="The full name of the organisation.")
    role: Role = Field(description="The role of the organisation as defined in the MARC Code List for Relators. Output the code of the role.")
    
class StructuredOutputSchema(BaseModel):
    subject_headings: Optional[str] = Field(description="[Source: Zone 1 (Top-Margin Annotation Zone)] The subject headings of the work. Subject headings are always handrwritten and located in the top right corner of the card. Capture exactly what is stated, including any letters, numbers, dots or spaces.")
    classification: Optional[str] = Field(description="[Source: Zone 1 (Top-Margin Annotation Zone)] The classification of the work, telling where the work is physically placed. Classification is always handwritten and located in the top left corner of the card. Capture exactly what is stated, including parentheses, brackets and other characters.")
    title_statement: Title = Field(description="[Source: Zone 2 (Top Header Block) & Zone 3 (Title Block)] Title and statement of responsibility. When there is no author, part of the title is the main entry of the card (Zone 2). You MUST logically reassemble the full title by combining the Main Entry with the Title Block, as defined in the Logical Assembly rule.")
    main_author: Optional[Person] = Field(description="[Source: Zone 2 (Top Header Block (Main Entry))] The main author of the work, usually to the person chiefly responsible for the work.")
    additional_persons: List[Person] = Field(description="[Source: Zone 2 (Top Header Block (Main Entry)) & Zone 3 (Title Block)] The contributors to the work. Do not include the same person more than once, not even with different roles. If a person has multiple roles in relation to the work, pick the most relevant one. If a person is listed as the main author, do NOT include them in the list of additional persons.")
    main_organisation: Optional[Organisation] = Field(description="[Source: Zone 3 (Title Block)] The main organisation responsible for the work. According to various cataloging rules, main entry under corporate name is assigned to works that represent the collective thought of a body. This corresponds to field 110 Main Entry-Corporate Name in MARC21.")
    additional_organisations: List[Organisation] = Field(description="[Source: Zone 3 (Title Block)] Additional organisations contributing to the work. This field corresponds to field 710 Added Entry-Corporate Name in MARC21.")
    publication_type: PublicationType = Field(description="""Determine the type of publication described on the card. Classify it as one of three options using the following criteria:
            monograph: Select for a single, self-contained work with a single publication year WITHOUT volume designation or volume enumeration. If a volume designation is present, it IS NOT a monograph.
            periodical: Select for publications issued continuously over time. Key indicators are an open-ended date range (e.g., '1952-') or sequential numbering for regular issues (e.g., 'Årg.', 'Vol.', 'Session').
            multi-volume: Select for a complete work published in a finite, specified number of parts. Key indicators are a volume designation with a closed range of volumes (e.g., 'D. 1-4', '1-5') and a corresponding closed date range (e.g., '1848-49'). The card might also describe a single volume, in which case look for a volume designation (like 'Vol. 1', 'D. 2', '1') and a single publication year."""
    )
    iso_language_name: str = Field(description="The full ISO English name of the primary language.")
    iso_language_code: str = Field(description="The ISO 639-2/B bibliographic code for the language.")
    editions: List[Edition] = Field(description="[Source: Zone 4 (Edition & Publication Stack)] List of editions of the work. There might be one or more editions. An edition always has a specified format, edition, format, location of publication and year of publication are printed on the same line like so: Format Place of publication Year(s). If the card describes a facsimile (a copy or reproduction), do NOT include the original, non-facsimile edition in the list of editions. Put the non-facsimile edition in the list of related works. Reference cards do not list editions.")
    related_works: List[RelatedWork] = Field(description="[Source: Zone 5 (Secondary Notes & Relations Zone)] List of related works mentioned on the card. Only look for the EXPLICIT indicators for different relation types. Do NOT infer the relation from the text following these indicators, e.g. the title of the related work. Capture all information you can find about the related work, e.g. author, title, location, format, year and edition.")
    is_diss: bool = Field(default=False, description="[Source: Zone 5 (Secondary Notes & Relations Zone)] A Boolean flag. TRUE if the term 'Diss.' or similar is EXPLICITLY visible. FALSE otherwise. Do NOT infer is_diss from a title or any other information.")
    diss_string: Optional[str] = Field(description="[Source: Zone 5 (Secondary Notes & Relations Zone)] If this is a dissertation, capture exactly what it says. Sometimes the term 'Diss.' is followed by more terms, often a geographic place.")
    is_reference_card: bool = Field(description="[Source: Zone 2 (Top Header Block (Main Entry))] A Boolean flag. TRUE if a plus sign ('+') is EXPLICITLY visible immediately preceding, above, or clearly marking the MAIN ENTRY (Title or Author) field of the card. FALSE otherwise.")

# 
# CONFIGURATION
#

JOBS_DIR = "/Users/xkumag/dev/kat-57-pipeline/jobs"
IMAGES_BASE_DIR = "/Users/xkumag/dev/kat-57-pipeline/source-input/all-images/20-batch"
OUTPUT_JSON = "extraction_error_rerun_requests.json"
IMAGE_EXTENSION = ".jpg" 

TARGET_JOB_PREFIX = "phase1_extraction_" 

SYSTEM_INSTRUCTION = "### ROLE\nYou are an expert librarian and archivist. Your task is to meticulously parse an input image of a library catalog card and extract all relevant data points into the provided JSON schema. \n\n### CONTEXT & STANDARDS\n* The catalog card strictly conforms to the Prussian Instructions (Preu\u00dfische Instruktionen) for cataloging. Apply your knowledge of this specific standard when you extract the data.\n* The information on the card may be in various languages. Pay close attention to accurate transcription of non-English characters and diacritics.\n\n### DOCUMENT GEOGRAPHY & LAYOUT\nThe library card is a horizontally oriented rectangle. The text is generally typewritten and organized into distinct spatial zones.\n\n**Important Note on Dynamic Layout:** The spatial zones do not have fixed coordinates. The layout is dynamic and cascading; the exact position of a zone is entirely dependent on the size of the zones above it. A multi-line title will push the publication data and footers further down the card. You must read the layout relatively, identifying where one block of text ends and the next begins based on whitespace, indentation, and standard cataloging sequence.\n\n* **Zone 1: Top-Margin Annotation Zone:**\n* **Relative Location:** The extreme upper edge of the card, sitting completely above all structured typewritten text.\n  * **Visual Structure:** Almost exclusively handwritten (often in pencil). The notes are usually isolated into the extreme left, center, and right areas with significant whitespace between them.\n  * **Content Mapping & Alignment:**\n    * **Extreme Upper-Left:** Contains notes on classification.\n    * **Middle:** Contains notes on a specific collection or shelfmark.\n    * **Extreme Upper-Right:** Contains subject headings.\n\n* **Zone 2: Top Header Block (Main Entry):**\n    * **Relative Location:** The highest structured, typewritten line on the card. This serves as your primary spatial anchor for the rest of the document. It usually starts near the left margin.\n    * **Visual Structure:** Typically a single line or short block of text. It frequently features an underline. Occasionally, it is prefixed with a plus sign ('+') to indicate a reference card.\n    * **Content Mapping & Alignment:** Contains the main entry, which is either an author or a grammatical ruling word from the title, formatted in strict accordance with the Prussian Instructions (Preu\u00dfische Instruktionen).\n\n* **Zone 3: Title Block:**\n    * **Relative Location:** Located immediately below the Main Entry (Zone 2). The vertical size of this block varies wildly depending on the length of the title.\n    * **Visual Structure:** This is usually the densest paragraph of text. Crucially, the very first line of this block is noticeably indented to the right compared to the Main Entry above it.\n    * **Content Mapping & Alignment:** Contains the primary title of the work, subtitles, and statement of responsibility.\n\n* **Zone 4: Edition & Publication Stack:**\n    * **Relative Location:** Located immediately below the Title Block. Its exact vertical starting position is strictly dependent on the length of the title above it.\n    * **Visual Structure:** This area functions as a vertically stacked list of editions or manifestations. Entries are arranged row by row. Even if there is only a single edition present, evaluate it as a stack of one. Occasionally, thin horizontal printed lines divide these rows.\n    * **Content Mapping & Alignment:** Each row in this stack may contain a combination of the following data points, which follow consistent spatial alignments:\n        * **Edition Statement & Volume Designation:** (e.g., \"2a upplagan.\", \"Vol. 1-3\", \"T. 1-4.\"). When present, these are typically aligned to the left side or center of the card.\n        * **Format, Place, and Year of Publication:** (e.g., \"8:o\", \"Stockholm\", \"1934\"). This specific trio of information is almost always grouped together in a strict sequence and strongly aligned to the right side of the card.\n        * **Serial Title:** The title of a series the work belongs to. This usually spans horizontally across the middle of the card, positioned below the specific edition.\n\n* **Zone 5: Secondary Notes & Relations Zone:**\n    * **Relative Location:** Located strictly below the Edition & Publication Stack. This is the final layout area and is frequently entirely blank.\n    * **Visual Structure:** This zone acts as a catch-all area for tertiary metadata. The information here often appears as isolated, distinct lines or short paragraphs.\n    * **Content Mapping & Alignment:** The data points found here are entirely independent of one another, but they share this bottom spatial area. Look for highly specific, literal string indicators:\n        * **Relations to Other Works:** These notes explicitly link the card to another physical volume or title. They always begin with specific Swedish relational strings (e.g., \"Smtr. med:\", \"Ur:\", \"Sammanbunden med:\", \"Forts. av\") followed by the related title information.\n        * **Dissertation Notes:** This indicates the work is a thesis. It is characterized by the explicit presence of the exact abbreviation \"Diss.\". This often sits entirely alone on its own line, or is followed closely by a university name or academic series.\n\n\n### EXTRACTION RULES & LOGIC\nYour goal is to populate the JSON schema with logically complete and accurately formatted data based on the card's contents. Apply the following principles:\n* **Schema Pointers:** Many field descriptions in the JSON schema begin with a `[Source: Zone X]` prefix. This is a strict spatial directive. When you see this, you MUST restrict your primary visual search for that specific data point to the defined spatial zone. If a field lacks this prefix, evaluate the entire card or apply logical derivation as required by the schema.\n* **Logical Assembly (The Prussian Instructions Rule):** You must reconstruct full semantic units even if they are visually split across multiple zones. Under PI, the main entry (Zone 2) is frequently the first word or the grammatical ruling word of the title. When extracting the full `title`, you must intelligently reassemble the title by combining the relevant word(s) from the Main Entry with the text in the Title Block (Zone 3) so that the output reads as a complete, natural title.\n* **Format & Parse According to Schema:** The JSON schema has ultimate authority over formatting. You are expected to parse complex visual strings into the formats requested by the schema. This includes resolving date spans into single integers if requested, extracting specific substrings, and mending obvious historical typos or cataloger errors to create clean data.\n* **Derived Fields (Controlled Inference):** For high-level classification fields (e.g., Country of Publication, Publication Type), use your world knowledge to infer the correct value based strictly on the visible text (e.g., inferring the country from a printed city).\n* **Strict Anti-Hallucination:** While you are expected to reassemble and format the text, you are STRICTLY FORBIDDEN from inventing facts. Do not guess authors, dates, or titles that are not physically represented somewhere on the card. If a data point cannot be found or logically derived from the visible text, output `null`.\n* **No Extraneous Text:** Output ONLY the valid JSON object.\n\n### STRICT ENCODING CONSTRAINTS\n* NEVER output control characters or non-printing characters.\n* NEVER use HTML entities (e.g., &amp;, &#39;) to represent special characters. Output the actual unicode characters.\n* You are STRICTLY FORBIDDEN from using escape sequences in your output outside of standard JSON formatting requirements."
TEXT_PROMPT = "Analyze the attached library catalog card. Extract the metadata exactly as defined in the system instructions and populate the JSON schema."


def collect_retry_requests():

    retry_requests = []
    missing_images = 0
    success_count = 0

    jobs_dir = Path(JOBS_DIR).expanduser().resolve()

    for batch_folder in jobs_dir.iterdir():
        
        if not batch_folder.match(f"{TARGET_JOB_PREFIX}*"):
            continue
        
        batch_path = Path(JOBS_DIR) / batch_folder
        
        if not batch_path.is_dir():
            continue
            
        # Extract the batch identifier and batch number (e.g., "batch31" from "phase1_extraction_batch31")
        batch_match = re.search(r'(batch(\d+))', batch_folder.name)
        if not batch_match:
            continue
        batch_id = batch_match.group(1)
        batch_number = batch_match.group(2)
        
        fail_dir = batch_path / "parse" / "fail"
        
        if not fail_dir.exists() or not fail_dir.is_dir():
            continue

        for error_file in fail_dir.iterdir():
            if error_file.match("*_error.json"):
                # Extract the request key
                request_key = re.sub(r'_[a-zA-Z0-9]+_error\.json$', '', error_file.name)
                
                # Locate the corresponding image
                image_dir = Path(IMAGES_BASE_DIR) / f"batch-{batch_number}"
                
                image_path = image_dir / f"{request_key}{IMAGE_EXTENSION}"
                
                if image_path.exists():
                    # Read and convert to base64
                    with open(image_path, "rb") as img_file:
                        encoded_string = base64.b64encode(img_file.read()).decode('utf-8')
                    
                    # Build the modular object
                    retry_requests.append({
                        "request_key": request_key,
                        "batch_id": batch_id,
                        "image_base64": encoded_string
                    })
                    success_count += 1
                else:
                    print(f"Warning: Image not found -> {image_path}")
                    missing_images += 1

    print(f"Finished! Collected {success_count} images for retry.")

    if missing_images > 0:
        print(f"Note: {missing_images} images could not be found.")

    return retry_requests


def build_request_objects(retry_requests, output_directory):

    tasks = []
    
    for request in retry_requests:
        
        parts =[
            InlineDataPart(type="inlineData", mimeType="image/jpeg", data=request["image_base64"]),
            TextPart(type="text", data=TEXT_PROMPT)
        ]

        task = PromptData(
            key=request["request_key"],
            prompt=[Content(role="user", parts=parts)],
            system_instruction=SYSTEM_INSTRUCTION,
            json_schema=StructuredOutputSchema.model_json_schema()
        )

        tasks.append(task)

    tasks_dicts = [task.model_dump() for task in tasks]

    print(output_directory)

    output_file = output_directory / OUTPUT_JSON
    with open(output_file, 'w') as fp:
        json.dump(tasks_dicts, fp, indent=4)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Process images in a directory.")
    parser.add_argument("--output_directory", type=Path, help="Path to where to put the json output")    
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed processing messages")
    args = parser.parse_args()

    images_to_retry = collect_retry_requests()

    build_request_objects(images_to_retry, args.output_directory)
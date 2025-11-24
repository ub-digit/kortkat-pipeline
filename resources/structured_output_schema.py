from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

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
    CONTIUES_AS = "continues-as"

class Edition(BaseModel):
    # Ev. upplagespecifik titel
    edition_statement: Optional[str] = Field(description="A specification of the edition (e.g. '3 uppl.', '3 edition' or similar).")
    volume_designation: Optional[str] = Field(description="The enumeration of the volume, e.g. 'Vol. 1', 'T. 2', 'D. 3', 'Årg 1-3' or similar. For periodicals, this can also include a year.")
    format: Optional[str] = Field(description="The physical format of the volume, e.g. '4:o', '8:o', '12:o', 'Fol'")
    place_of_publication: List[str] = Field(description="Where the work was published or printed. If 'u.o.' is stated, there is no known place of publication, and should render a null value.")
    country_of_publication: List[str] = Field(description="ISO 3166 English name of the country where the place of publication is located")
    year_of_publication: Optional[int] = Field(ge=1000, description="When the work was published or printed. If 'u.å.' is stated, there is no known year, and should render a null value.")
    year_of_publication_exact_string: Optional[str] = Field(description="When the work was published or printed. If 'u.å.' is stated, there is no known year. Capture EXACTLY what is stated.")
    year_of_publication_compact_string: Optional[str] = Field(
        description=(
            "A compact string representing the year or years of publication, following a specific grammar. The output MUST strictly adhere to these rules:"
            "**Single Year**: Use a four-digit format 'YYYY'. Example: '1984'."
            "**Multiple Items**: Use a comma ',' without spaces to separate distinct years or ranges. Example: '1984,1992'."
            "**Closed Range**: For a continuous range of years, use a hyphen '-' between the start and end year. Example: '1990-1995'."
            "**Open Range**: For an ongoing publication, use the start year followed by a hyphen. Example: '2010-'."
            "**Combinations**: Combine these rules for complex cases. For a card listing years 1850, 1852, the period from 1901 to 1910, and an ongoing series started in 1925, the correct output is '1850,1852,1901-1910,1925-'."
        )
    )
    serial_titles: List[str] = Field(description="List of serial titles the edition is part of. A reference to a serial title can be indicated in several different ways: prefixed with an equal sign (“=”), enclosed in slashes (“/”) or parentheses. Sometimes there is no specific indication except for the title of the serial. Information on volume etc can also be included in the reference. The reference to the serial is written below each edition.")

class RelatedWork(BaseModel):
    relation_type: RelationType = Field(
        description=(
            "The type of relation."
            "Use 'bound-with' for works that are bound together. This relation is indicated with the words 'Sammanbunden med:', 'Sammanb. med:', 'Smb. med:' or similar being EXPLICITLY visible followed by the related title."
            "Use 'therewith-bound for works that are bound together. This relation is indicated with the words 'Därm. smb.', 'Därmed smb.', 'Därmed sammanbunden', 'Därmed sammanb.', 'Därm. sammanb.' or similar being EXPLICITLY visible followed by the related title."
            "Use 'printed-with' for works that are printed together. This relation is indicated with the words 'Smtr. med:', 'Sammantryckt med:', 'Sammantr. med:' or similar being EXPLICITLY visible followed by the related title."
            "Use 'therewith-printed' for works that are printed togheter. This relation is indicated with the words 'Därmed smtr.:', 'Därm. Smtr.:', 'Därmed sammantryckt:', 'Därm. Sammantryckt:', 'Därm. sammantr.:' or similar being EXPLICITLY visible followed by the related title."
            "Use 'contribution' when the work described on the card is a part of another work, for example an article or a chapter. This relation is indicated with the word 'i:' being EXPLICITLY visible followed by the related title."
            "Use 'offprint' when the card describes an offprint. This relation is indicated with the word 'Ur:', 'Särtryck ur' or similar being EXPLICITLY visible followed by the related title."
            "Use 'facsimile' when the word 'Faksimil', 'Faksimilupplaga' or similar is noted on the card."
            "Use 'continuation-of' when the card describes a work that continues another work. This relation is indicated with the words 'Forts. av', 'Forts. på', 'Fortsättning av', 'Fortsättning på' or similar being EXPLICITLY visible followed by the related title."
            "Use 'continues-as' when the card describes a work that is continued by another work. This relation is indicated with the words 'Forts. se:' being EXPLICITLY visible followed by the related title."
        )
    )
    related_author: Optional[str] = Field(description="The author of the related work.")
    related_title: Optional[str] = Field(description="The title of the related work.")
    related_location: Optional[str] = Field(description="The location of the related work.")
    related_format: Optional[str] = Field(description="The format of the related work.")
    related_year: Optional[int] = Field(description="The year of publication of the related work.")
    related_edition: Optional[str] = Field(description="The edition of the related work.")
    
class StructuredOutputSchema(BaseModel):    
    title: str = Field(description="The title of the work.")
    author: Optional[str] = Field(description="The author of the work.") # Ev. author list, med specat förnamn och efternamn
    publication_type: PublicationType = Field(
        description=(
            "Determine the type of publication described on the card. Classify it as one of three options using the following criteria:"
            "monograph: Select for a single, self-contained work with a single publication year WITHOUT volume designation or volume enumeration. If a volume designation is present, it IS NOT a monograph."
            "periodical: Select for publications issued continuously over time. Key indicators are an open-ended date range (e.g., '1952-') or sequential numbering for regular issues (e.g., 'Årg.', 'Vol.', 'Session')."
            "multi-volume: Select for a complete work published in a finite, specified number of parts. Key indicators are a volume designation with a closed range of volumes (e.g., 'D. 1-4', '1-5') and a corresponding closed date range (e.g., '1848-49'). The card might also describe a single volume, in which case look for a volume designation (like 'Vol. 1', 'D. 2', '1') and a single publication year."
        )
    )
    iso_language_name: str = Field(description="The full ISO English name of the primary language.")
    iso_language_code: str = Field(description="The ISO 639-2/B bibliographic code for the language.")
    editions: List[Edition] = Field(description="List of editions of the work. There might be one or more editions. An edition always has a specified format, edition, format, location of publication and year of publication are printed on the same line like so: Format Place of publication Year(s). If the card describes a facsimile (a copy or reproduction), do NOT include the original, non-facsimile edition in the list of editions. Put the non-facsimile edition in the list of related works. Reference cards do not list editions.")
    related_works: List[RelatedWork] = Field(description="List of related works mentioned on the card. Only look for the EXPLICIT indicators for different relation types. Do NOT infer the relation from the text following these indicators, e.g. the title of the related work. Capture all information you can find about the related work, e.g. author, title, location, format, year and edition.")
    is_diss: bool = Field(default=False, description="A Boolean flag. TRUE if the term 'Diss.' or similar is EXPLICITLY visible. FALSE otherwise. Do NOT infer is_diss from a title or any other information.")
    diss_string: Optional[str] = Field(description="If this is a dissertation, capture exactly what it says. Sometimes the term 'Diss.' is followed by more terms, often a geographic place.")
    is_reference_card: bool = Field(
        description="A Boolean flag. TRUE if a plus sign ('+') is EXPLICITLY visible immediately preceding, above, or clearly marking the MAIN ENTRY (Title or Author) field of the card. FALSE otherwise."
    )
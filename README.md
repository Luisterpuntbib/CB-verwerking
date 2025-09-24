# CB-verwerking Luisterpuntbibliotheek

Versie september 2025


## Uitleg

Dit script haalt de metadata van epub-bestanden op uit een vastgestelde hoofdbestandsmap met daarin geïmporteerde bestandsmappen. Na normaliseren van de metadata worden de boeken toegevoegd aan het bestaande overzichtsbestand, na bestaande info eventueel te hebben geüpdatet (bv. de actie-kolom aanpassen). Hierdoor wordt handmatig toegevoegde informatie niet verwijderd mits er geen nieuwe informatie 'overheen' wordt geschreven. Bestanden met nieuwe toevoegingen en het oude overzicht worden weggeschreven naar een archiefmap. Van pdf-bestanden worden ISBN, leverdatum, extensie en actie toegevoegd aan het overzicht; overige metadata moet momenteel handmatig worden toegevoegd. Nadat de metadata van een bestandsmap is opgehaald wordt de map als geheel verplaatst naar een archiefmap.


## Gebruik

Het script cb_verwerking_epubs.py verwacht een pad naar de hoofdmap die de bestandsmappen met epubs en pdfs bevat. Het overzichtsbestand wordt geplaatst in de hoofdmap, de archiefmap met daarin verschillende submappen staat ook in de hoofdmap. Als de paden correct zijn ingesteld, kan dit script als automatische taak worden gedraaid waarbij bijvoorbeeld iedere nacht nieuw toegevoegde mappen worden verwerkt.

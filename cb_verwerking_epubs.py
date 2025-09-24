import os
import shutil
import pandas as pd
import time
import xml.etree.ElementTree as ET
import glob
from tqdm import tqdm

import ebooklib
from ebooklib import epub

import warnings
# supress ignore_ncx
warnings.filterwarnings("ignore", message="In the future version we will turn default option ignore_ncx to True.")
warnings.filterwarnings("ignore", message="This search incorrectly ignores the root element.")

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(filename='log_example.log', encoding='utf-8', level=logging.DEBUG)

cb_map = ''
done_path = ''


def clean_isbn(isbn):
	'''
	[('9789025449926', {'id': 'p9789025449926'})] -> '9789025449926'
	'''
	clean_isbn = [i[0] for i in isbn][0]
	# als isbn langer is dan het juiste format een lege string invullen
	if len(clean_isbn) > 13:
		return ''
	return clean_isbn

def clean_title(title):
	'''
	[('Het wonderbaarlijke voorval met de hond in de nacht', {})] -> 'Het wonderbaarlijke voorval met de hond in de nacht'
	'''
	return [i[0] for i in title][0]

def clean_author(author):
	'''
	[('Mark Haddon', {'{http://www.idpf.org/2007/opf}role': 'aut'})] -> 'Mark Haddon'
	[('Mark Haddon', 'Bob Dylan', {'{http://www.idpf.org/2007/opf}role': 'aut'})] -> 'Mark Haddon, Bob Dylan'
	'''
	# [] -> ''
	if ''.join(str(x) for x in author) == '':
		return ''
	author_tuple = [i[:-1] for i in author][0]
	# [(None, {})] -> ''
	if author_tuple[0] == None:
		return ''
	return ', '.join(author_tuple)

def clean_publisher(publisher):
	'''
	[('Atlas Contact', {})] -> 'Atlas Contact'
	'''
	# [] -> ''
	if ''.join(str(x) for x in publisher) == '':
		return ''
	clean_publisher = [i[0] for i in publisher][0]
	# [(None, {})] -> ''
	if clean_publisher == None:
		return ''
	return clean_publisher

def clean_date(date):
	'''
	[('2016-01-01', {'{http://www.idpf.org/2007/opf}event': ''}), ('2016-08-09', {'{http://www.idpf.org/2007/opf}event': 'modification'})] -> '2016'
	'''
	if ''.join(str(x) for x in date) == '':
		return ''
	clean_date = [i[0] for i in date][0]
	# als het jaartal niet begint met een logische eeuw: een lege string gebruiken
	correct_centuries = ['20', '19', '18']
	if clean_date[:2] not in correct_centuries:
		return ''
	# gebruik alleen het jaartal uit clean_date: '2016-08-09' -> '2016'
	return clean_date.split('-')[0]

def clean_language(language):
	'''
	[('nl', {})] -> 'nl'
	'''
	clean_lan = [i[0] for i in language][0]
	# 'nl-NL' -> 'nl'
	if clean_lan == 'nl-NL':
		return 'nl'
	return clean_lan.lower()

def get_metadata_epub(file_path):
	# epub-bestand inlezen, foutmelding geven als er iets misloopt
	try:
		book = epub.read_epub(file_path)
	except Exception as e:
		logger.error(f"Error reading EPUB file: {e}")

	# benodigde attributen oplijsten en ophalen uit epub-bestand
	# auteur heet hier 'creator' (wordt later nog aangepast in de export)
	# attributes = ['identifier', 'title', 'creator', 'publisher', 'date', 'language']
	attributes = ['title', 'creator', 'publisher', 'date', 'language']
	metadata = {attr: book.get_metadata('DC', attr) for attr in attributes}

	return metadata

# Cleaning-functies één voor één aanroepen en toepassen op overeenkomend attribuut en eventuele errors loggen
def clean_metadata(metadata):
	funcs = [
		# lambda: metadata.update({'identifier': clean_isbn(metadata.get('identifier', ''))}),
		lambda: metadata.update({'title': clean_title(metadata.get('title', ''))}),
		lambda: metadata.update({'creator': clean_author(metadata.get('creator', ''))}),
		lambda: metadata.update({'publisher': clean_publisher(metadata.get('publisher', ''))}),
		lambda: metadata.update({'date': clean_date(metadata.get('date', ''))}),
		lambda: metadata.update({'language': clean_language(metadata.get('language', ''))})
	]

	for func in funcs:
		try:
			func()
		except Exception as exc:
			logger.debug(f"Error cleaning metadata: {exc}")
			pass

	return metadata

def add_filename_info(file, clean_metadata_dict):
	'''
	'20240710223036_9789493341227.epub' -> '9789493341227' en '20240710'
	'''
	clean_metadata_dict['ISBN'] = file.split('_')[1].split('.')[0]
	clean_metadata_dict['Leverdatum'] = file.split('_')[0][:-6]
	clean_metadata_dict['Extensie'] = file.split('.')[1]

	return clean_metadata_dict

def append_to_merged_dicts(clean_metadata_dict_isbn, merged_dict):
	'''
	Voeg metadata-dict van epub toe aan merged_dict met metadata van epubs uit de bestandsmap
	clean_metadata_dict = {'a': '4', 'b': '5', 'c': '6'} ->
	merged_dict = {'a': ['1', '4'], 'b': ['2', '5'], 'c': ['3', '6']}
	'''
	for key, value in clean_metadata_dict_isbn.items():
		if key in merged_dict:
			merged_dict[key].append(value)
		else:
			merged_dict[key] = [value]
	return merged_dict

# EAN en operatie vanuit xml toevoegen aan nieuw df
def xml_data(bestandsmappaden):
	data = []
	for bestandsmappad in bestandsmappaden:
		xml_files = [x for x in os.listdir(bestandsmappad) if x.endswith(".xml")]
		for xml_file in xml_files:
			root = ET.parse(os.path.join(bestandsmappad, xml_file)).getroot()
			# ean en operation, leverdatum in id parsen en toevoegen aan lijst
			for content in root.findall(".//{http://www.cbonline.nl/xsd}content"):
				ean = content.find("{http://www.cbonline.nl/xsd}ean").text
				operation = content.find("{http://www.cbonline.nl/xsd}operation").text
				# leverdatum = root.attrib.get("id")[:8]
				data.append({"ISBN": ean, "Actie": operation}) #, "Leverdatum": leverdatum})
	# zorg dat altijd een geldige DataFrame wordt teruggegeven
	if data:
		return pd.DataFrame(data)
	else:
		return pd.DataFrame(columns=['ISBN', 'title', 'creator', 'publisher', 'date', 'language', 'Leverdatum', 'Extensie', 'Actie'])

def update_overzichtsbestand(df_origineel, df_nieuw):
	'''
	Combineert het bestaande overzichtsbestand met nieuw opgehaald info
	Nieuwe boeken worden als nieuwe rijen toegevoegd,
	Bestaande boeken met nieuwe info (bv nieuwe actiecode) worden overschreven
	'''
	# merge met suffix voor oude kolommen
	df_gecombineerd = df_overzicht.merge(df_nieuw, on='ISBN', how='outer', suffixes=('_oud', ''))

	# overschrijf oude waarden met nieuwe indien beschikbaar
	for kolom in df_nieuw.columns:
		if kolom != 'ISBN':
			df_gecombineerd[kolom] = df_gecombineerd[kolom].combine_first(df_gecombineerd[f"{kolom}_oud"])

	# verwijder de oude kolommen
	df_gecombineerd.drop(columns=[f"{kolom}_oud" for kolom in df_nieuw.columns if kolom != 'ISBN'], inplace=True)

	return df_gecombineerd

def verplaats_verwerkte_map(verwerkte_mappen, done_path):
	'''
	Mappen in de hoofdmap na verwerking in geheel verplaatsen naar de done-map
	'''
	for file_path in verwerkte_mappen:
		shutil.move(file_path, done_path)

uitgesloten_paden = {'done', 'pdfs', 'fictief', 'archief'}

# Lijst van alle submappen in cb_map die geen uitgesloten naam hebben
geldige_paden = [
	os.path.join(cb_map, d)
	for d in os.listdir(cb_map)
	if os.path.isdir(os.path.join(cb_map, d)) and d not in uitgesloten_paden
]

merged_dict = {}
merged_pdf_dict = {}

# functie aanroepen, gegevens per boek verzamelen in dict en toevoegen aan merged_dict/merged_pdf_dict
for file_path in tqdm(geldige_paden, desc="Verwerken van paden"):
	for file in os.listdir(file_path):
		if file.endswith('.epub'):
			full_path = os.path.join(file_path, file)
			metadata_epub = get_metadata_epub(full_path)
			clean_metadata_dict = clean_metadata(metadata_epub)
			clean_metadata_dict_isbn = add_filename_info(file, clean_metadata_dict)
			append_to_merged_dicts(clean_metadata_dict_isbn, merged_dict)
		elif file.endswith('.pdf'):
			filename_info_pdfs = add_filename_info(file, {})
			append_to_merged_dicts(filename_info_pdfs, merged_pdf_dict)

# epub-dict omzetten naar df, checken of de dict niet leeg is (anders alleen een isbn-kolom)
merged_df = pd.DataFrame.from_dict(merged_dict) if merged_dict else pd.DataFrame(columns=['ISBN'])
# pdf-dict omzetten naar df en toevoegen aan merged_df (een lege df krijgt alleen een isbn-kolom)
pdf_df = pd.DataFrame.from_dict(merged_pdf_dict) if merged_pdf_dict else pd.DataFrame(columns=['ISBN'])
merged_df = pd.concat([merged_df, pdf_df], ignore_index=True)
# xml-data ophalen als df
df_xml = xml_data(geldige_paden)
# xml-data mergen met merged_df, waarbij xml-data zonder match ook wordt toegevoegd
merged_df = pd.merge(merged_df, df_xml, on='ISBN', how='right', indicator=False)

# juiste volgorde en namen van kolomkoppen instellen
juiste_volgorde = ['ISBN', 'title', 'creator', 'publisher', 'date', 'language', 'Leverdatum', 'Extensie', 'Actie']
merged_df = merged_df[juiste_volgorde]
merged_df = merged_df.rename(columns={'title': 'Titel', 'creator': 'Auteur(s)', 'publisher': 'Uitgever', 'date': 'Publicatiejaar', 'language': 'Taal'})

# bestaand overzichtsbestand ophalen (aanname dat er maar één overzichtsbestand in de cb-map staat) en nieuwe data toevoegen aan bestaand overzicht
bestaand_overzichtsbestand = glob.glob(cb_map + 'overzicht_metadata_CB_*.xlsx')

if bestaand_overzichtsbestand:
	overzicht = bestaand_overzichtsbestand[0]
	alle_sheets = pd.read_excel(overzicht, sheet_name=None, engine='openpyxl')
	# sheets samenvoegen tot één df
	df_overzicht = pd.concat(alle_sheets.values(), ignore_index=True)
	df_overzicht['ISBN'] = df_overzicht['ISBN'].astype(str)
	# bestaand overzichtsbestand samenvoegen met nieuw opgehaalde info
	nieuw_overzicht = update_overzichtsbestand(df_overzicht, merged_df)
else:
	print("Er ging iets mis met het inlezen van het excel-bestand.")

# verwerkte mappen verplaatsen naar verwerkt-map
verplaats_verwerkte_map(geldige_paden, done_path)
print(f"Verwerkte mappen verplaatst naar {done_path}")

# output-bestand naar archiefmap (alleen de nieuw toegevoegde info)
bestandsnaam_output = cb_map + 'archief/archiefbestand_metadata_CB_' + time.strftime("%Y%m%d") + '.xlsx'
merged_df.to_excel(bestandsnaam_output, index=False)
print(f"Archiefbestand {bestandsnaam_output} staat klaar.")

# aangevuld overzichtsbestand als output cb-map (bestaande én nieuw toegevoegde info), verdeeld over tabbladen per actie
bestandsnaam_output = cb_map + 'overzicht_metadata_CB_' + time.strftime("%Y%m%d") + '.xlsx'
nieuw_overzicht.to_excel(bestandsnaam_output, index=False)
print(f"Overzichtsbestand {bestandsnaam_output} staat klaar.")

# oude overzichtsbestand verplaatsen naar archiefmap
overzichtsbestanden_pad = cb_map + 'archief/oude overzichtsbestanden/'
shutil.move(overzicht, overzichtsbestanden_pad)
print(f"Het oude overzichtsbestand is verplaatst naar het archief.")

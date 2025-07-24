import pandas as pd
import streamlit as st
import logging
from shared import pdf_reader



#######################

DEBUG = False

def st_print_partitions(partitions):

   for doc_partition in partitions:
      classification = doc_partition.classification
      display_object = doc_partition.display_object
      props = doc_partition.props
      words_df = doc_partition.words_df
      
      # Text
      if (classification == "TEXT"):
         if classification == "FOOTER":
            class_tag = "(footer)"
         else:
            class_tag = ""
         text = display_object
         text_size = props.get("text_height")
         is_bold = props.get("is_bold")
         is_italic = props.get("is_italic")

         st_print_text(text, text_size, is_bold, is_italic)

         if DEBUG:
            st.write(f"({classification})")
            st.dataframe(words_df)
            #st.write(props)

      elif (classification == "LIST"):
         
         for bullet, text in display_object:
            st.write()
            st_print_text(bullet + " " + text) #, text_size, is_bold, is_italic)
         #text = display_object.replace("$", "\\$")
         #text_size = props.get("text_height")
         #is_bold = props.get("is_bold")
         #is_italic = props.get("is_italic")

         

         if DEBUG:
            st.write(f"({classification})")
            st.dataframe(words_df)
            #st.write(props)

   
      elif classification == "TABLE":
        print("\nTABLE>>")
        pd.set_option("display.max_rows", None)
        pd.set_option("display.max_columns", None)
        if DEBUG:
           st.write(f"({classification})")
        st.dataframe(display_object) #, hide_index=True)


def st_print_text(text, size=10, is_bold=None, is_italic=None):
   # Size of text
   header_level = ""
   if size > 20:
      header_level = "# "
   elif size > 16:
      header_level = "## "
   elif size > 12:
      header_level = "### "

   # Bold/italics
   style = ""
   if is_bold and is_italic:
      style = "***"
   elif is_bold:
      style = "**"
   elif is_italic:
      style = "*"
   
   # Print
   text = text.replace("$", "\\$")
   st.markdown(header_level + style + text + style)

###
###


st.title("PDF Parser")

st.write("""
Utility to parse 
""")

uploaded_file = st.file_uploader("Upload a file")
page = st.number_input("Page", min_value=1, max_value=100, step=1, format="%d")

filename = uploaded_file

#filename = "universities\\cds\\brown_CDS_2024_2025.pdf"
#filename = "universities\\yale-fy24-financial-report-10_25_24.pdf"
#page = 41 # page = [36, 41]






# This is essentially a direct call from pdfplumber
if not uploaded_file:
   st.write("Please enter file above.")
   
else:

   _, words, page_props = pdf_reader.read_pdf_pages_from_filepath(filename, page)
   words_df = pd.DataFrame(words)
   words_df = words_df.round(1)
   
   if len(words_df) == 0:
      st.warning("No text found in the PDF.")
      

   page_layout_elements: dict = pdf_reader.estimate_page_layout(words_df, page_props)

   for layout_type, df in page_layout_elements.items():
      st.header(layout_type)
      if len(df) > 0: 
         partitions = pdf_reader.partition_words(df, page_props)
         st_print_partitions(partitions)

   #partitions = partition_words(words_df, page_props)


   words_df = pdf_reader.cluster_nearby_words_xaxis(words_df)
   pd.set_option('display.max_rows', None)
   #pprint.pprint(words_df)

   words_df["bottom"] = words_df["top"] + words_df["height"]




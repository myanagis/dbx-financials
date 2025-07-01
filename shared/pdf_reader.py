
import pdfplumber
from intervaltree import IntervalTree
import pandas as pd
import numpy as np
import pprint
from collections import defaultdict, Counter
import tabulate
from enum import Enum
import re
import logging

###################################
# GENERIC HELPERS 
###################################

def is_within_tolerance(val0, val1, tolerance):
  return abs(val0 - val1) < tolerance

def is_within_tolerance_for_dicts(dict1, dict2, key, tolerance):
   val1 = dict1.get(key)
   val2 = dict2.get(key)
   if (val1 is None) or (val2 is None):
      return False
   return is_within_tolerance(val1, val2, tolerance)

###################################
# TOLERANCES
###################################

def get_maximum_space_width(text_height):
   # Based on testing, on font size ~7, space needs to be greater than ~4
   # On font size 11, a space is about 4.5-5

   # A ChatGPT search that a space character takes up about 1/4 to 1/3 of the font size,
   # meaning that a space is up to 3.6

   # I think a safe max_space_width for now is 0.3*height. This visually works well 
   # for testing, but can adjust as needed
   return text_height*0.4

def get_maximum_nonspace_width(text_height):
   # Sometimes, pdfplumber adds in a space that shouldn't really exist (especially for numbers).
   # Therefore, it helps to have a "tolerance" for re-smushing two word fragments back together.

   # A tolerance of 0.2 for a text height of 11 seemed reasonable. This is about 2%
   return text_height*0.02

def get_height_tolerance():
   return 0.1

def get_min_tab_space_width(text_height):
   # In one case: 36pts tab, 11 pt font. Be conservative with 2.5
   # (Actually, 36 is 1/2 an inch .. probably pretty common)
   return 30

###################################
# WORD CLUSTERING 
###################################


def cluster_nearby_words_xaxis(words_df: pd.DataFrame):

  # Initial sort by "top", then "x0"
  words_df_sorted = words_df.sort_values(by=["top", "x0"]).reset_index(drop=True)

  #pprint.pprint(words_df_sorted)

  # Initialize the algorithm by getting the current group
  keys = ["text", "x0", "x1", "top", "bottom", "height", "direction", "is_bold", "is_italic"]
  row = words_df_sorted.loc[0]
  current_group = {k: row[k] for k in keys}
   
  groups = []

  # Loop through all subsequent rows
  for i in range(1, len(words_df_sorted)):
     
     # Queue up the next word
     row_slice = words_df_sorted.loc[i]
     row = {k: row_slice[k] for k in keys}


     # Conditions for a match:
     # 1. Same "top" value
     max_top_tolerance = 3
     is_same_line = is_within_tolerance_for_dicts(current_group, row, "top", max_top_tolerance)
     # 2. Same height
     max_height_tolerance = get_height_tolerance()
     is_same_height = is_within_tolerance_for_dicts(current_group, row, "height", max_height_tolerance)
     # 3. Same direction
     is_same_direction = (current_group.get("direction") == row.get("direction"))
     # 4. Close x
     current_group_height = current_group.get("height", 0)
     max_x_tolerance = get_maximum_space_width(current_group_height)
     x_distance = row["x0"] - current_group["x1"]
     is_close_x = abs(x_distance) <= max_x_tolerance
     # 5. Is similar style (bold/italics)
     is_similarly_bolded = current_group.get("is_bold") == row.get("is_bold")
     is_similarly_italicized = current_group.get("is_italic") == row.get("is_italic")

     # debug
     """
     if row["text"] == "Cash":
        print("Current group: ", current_group)
        print("Row: ", row)
        print(f"Is same line: {is_same_line}")
     """

     # If it's a match, merge into current group
     if is_same_line and is_same_height and is_same_direction and is_close_x and is_similarly_bolded and is_similarly_italicized:
        delim = "" if x_distance <= get_maximum_nonspace_width(current_group_height) else " "
        current_group["text"] += delim + row["text"]
        current_group["x1"] = row["x1"]
    
     # Otherwise, it's not a match. Close out the prior group and start a new one.
     else:
        groups.append(current_group)
        current_group = {k: row[k] for k in keys}

  # At the end, close out the current group
  groups.append(current_group)
  
  # Return the df
  return pd.DataFrame(groups)




###################################
# PARTITIONING
###################################
import inspect

     
class DocPartition:
  def __init__(self, classification, display_object, props, words_df, warnings):
    self.classification = classification
    self.display_object = display_object
    self.props = props
    self.words_df = words_df
    self.warnings = warnings


# Group words by partitions
def find_partitions(words_df, type_of_partition, min_margin_height=6):
  
  # Allow for searching by vertical or horizontal partitions
  if type_of_partition == "horizontal":
     limit_key = "bottom"
     new_cluster_start_key = "top"
     sort_order=["top", "x0"]
  elif type_of_partition == "vertical":
     limit_key = "x1"
     new_cluster_start_key = "x0"
     sort_order=["x0", "top"]
  
  clusters = [] # This is a list of (list of dictionaries) (can be thought of as a list of DFs)

  # Initial sort by "top", then "x0"
  words_df_sorted = words_df.sort_values(by=sort_order).reset_index(drop=True)

  # Initialize the algorithm by getting the current group
  keys = ["text", "x0", "x1", "top", "bottom", "height", "direction", "is_bold", "is_italic"]
  row = words_df_sorted.loc[0]

  current_group = {k: row[k] for k in keys}
  current_cluster_end = current_group.get(limit_key)
  current_cluster = [] # This is a list of dictionaries (which can be converted into a DF)
  current_cluster.append(current_group)

  # Loop through all rows. Check: does the row fit into the current top/bottom?
  for i in range(1, len(words_df_sorted)):

    # Queue up the next word
    row_slice = words_df_sorted.loc[i]
    row = {k: row_slice[k] for k in keys}

    # Conditions for a match:
    #  1. Top of the new row and bottom of the old are close
    y_distance = row.get(new_cluster_start_key) - current_cluster_end
    is_close_y = y_distance <= min_margin_height # Don't take absolute value

    # If it's a match, then set the cluster top and bottom
    if is_close_y:
        # Update the bottom 
        current_cluster_end = max(current_cluster_end, row.get(limit_key))
        # Add the current row
        current_cluster.append(row)
        
    # Otherwise, it's not a match. Close out the prior cluster, and create a new one
    else:
        clusters.append(current_cluster)

        # Create new cluster
        current_group = {k: row[k] for k in keys}
        current_cluster_end = current_group.get(limit_key)
        current_cluster = []
        current_cluster.append(current_group)

  # At the end, close out the current group
  clusters.append(current_cluster)


  # Reformat the returns to be in dataframes
  clusters_by_df = []
  for cluster in clusters:
     clusters_by_df.append( pd.DataFrame(cluster) )

  return clusters_by_df

def find_max_gap(intervals): #TODO: rename
  
  # Sort first
  intervals_sorted = sorted(intervals, key=lambda x: x[0])
  gaps = []
  max_so_far = 0
  prior_x1 = 0

  for x0, x1 in intervals_sorted:
      if prior_x1 == 0:
        prior_x1 = x1
      else:
        width = x0 - prior_x1
        gaps.append(width)
        max_so_far = max(max_so_far, width)
        prior_x1 = x1

  return max_so_far

def calculate_partitions(words_df, how_to_partition_list):
  AUTO_MARGIN_TOLERANCE = 2
  """
  Calculates the partitions in the words_df, based on the list of "how to partition the list"
  Returns a list of partitions
  """

  returned_partitions_list = [words_df.copy()] # list of DFs

  # Continually partition the list based on the partition types
  for partition_tuple in how_to_partition_list:
    partition_type, margin = partition_tuple

    if margin == "auto":
      temp_vparts = find_partitions(words_df, partition_type, min_margin_height=1)
      v_heights = get_tuples_for_partition(temp_vparts, partition_type)
      margin = max(find_max_gap(v_heights) - AUTO_MARGIN_TOLERANCE, AUTO_MARGIN_TOLERANCE)
      

    tmp_list = []
    for df in returned_partitions_list:
      partitioned_dfs = find_partitions(df, partition_type, min_margin_height=margin)
      tmp_list += partitioned_dfs
    returned_partitions_list = tmp_list

  return returned_partitions_list

#import streamlit as st
def partition_words(words_df, page_props, how_to_partition= [("horizontal", "auto"), ("horizontal", 6)]):
   partitions = []

   #how_to_partition = [  ("horizontal", 8) , ("vertical", 8)] #[ ("vertical", 8), ("horizontal", 8) , ("vertical", 8)]
   
   partitions_dfs = calculate_partitions(words_df, how_to_partition)

   # First, try to partition by horizontal partitions
   
   #vert_partitions = find_partitions( words_df, "horizontal", min_margin_height=margin_height)

   # Next, try to partition by vertical partitions
   for v_partition_df in partitions_dfs:
      margin_height = 8
      horiz_partitions = find_partitions( v_partition_df, "vertical", min_margin_height=margin_height)
      classification = classify_chunk(v_partition_df, horiz_partitions)

      # Group the words together here, after we classify each section
      v_partition_df = cluster_nearby_words_xaxis(v_partition_df) # TODO

      # DEBUG
      #st.write(classification)
      #st.dataframe(v_partition_df)

      print(f"\nClassification: {classification}===========")
      #display(v_partition_df)
      
      # If it's a text, then just glue all the pieces together!
      if classification == "TABLE":
         partitions += parse_table(v_partition_df)
      elif classification == "LIST":
         print (" ... parsing list")
         partitions += parse_table(v_partition_df)
         #partitions += parse_list(v_partition_df)
      else: # TEXT
         returned_chunks = melt_text_rows_together(v_partition_df, classification)
         partitions += returned_chunks
         #pprint.pprint(v_partition_df)

   partitions = merge_similar_partitions(partitions, page_props)
   return partitions

def merge_similar_partitions(partitions, page_props):
   """
   This function is meant to "stitch" back together similar and adjacent partitions.
   Of note, try to stitch back together tables. 
   """
   returned_partitions = []
   last_classification = ""
   last_display_object = None
   last_props = {}
   last_words_df = pd.DataFrame()
   last_warnings = []

   for doc_partition in partitions: #$$$
      classification = doc_partition.classification
      display_object = doc_partition.display_object
      props = doc_partition.props
      words_df = doc_partition.words_df
      warnings = doc_partition.warnings
      
      # Check to see if (1) we have two tables and (2) the col widths "match".
      # If they do, just keep extending the table
      if (last_classification == "TABLE") and (classification == "TABLE") and do_col_widths_get_along( props.get("col_widths"), last_props.get("col_widths") ):
            
            ## If the columns match, then build the tables
            #if cols_match:
               last_words_df = pd.concat([last_words_df, words_df], ignore_index=True)
               table_partition = parse_table(last_words_df)

               doc = table_partition[0]
               last_classification = doc.classification
               last_display_object = doc.display_object
               last_props = doc.props
               last_words_df = doc.words_df
               warnings = doc.warnings
                                      
      else:
         # Save off whatever we have in the "last" part
         returned_partitions.append( DocPartition(last_classification, last_display_object, last_props, last_words_df, last_warnings) ) 
         

         # Set this for the next time
         last_classification = classification
         last_display_object = display_object
         last_props = props
         last_words_df = words_df
         last_warnings = warnings

   returned_partitions.append( DocPartition(last_classification, last_display_object, last_props, last_words_df, last_warnings) ) 
   return returned_partitions

BULLET_PATTERN = re.compile(r"^\s*[\u2022\-–\*]\s")

ENUM_PATTERN = re.compile(r"""
   ^\s*               # start of string, optional leading space
   \(?                # optional opening parenthesis
   [a-zA-Z0-9]{1,3}   # 1 to 3 characters (a, A, i, I, 1, 12, etc.)
   \)?                # optional closing parenthesis
   [\.\)]             # ends in dot or close paren
   \s                # followed by an optional string
""", re.VERBOSE)

def is_bulleted_list_item(text):
    return bool(BULLET_PATTERN.match(text))

def is_ordered_list_item(text):
    return bool(ENUM_PATTERN.match(text))

def is_list_like(text):
    return is_bulleted_list_item(text) or is_ordered_list_item(text) or (len(text) == 1)

def is_list_like_or_empty(text):
    if pd.isna(text) or str(text).strip() == "":
        return True
    return is_list_like(text)

def classify_chunk(words_df:pd.DataFrame, horiz_partitions: list):
   h_partition_count = len(horiz_partitions)
   if h_partition_count == 1:
      classification = "TEXT"
   # If it looks like a 2-column table, it could very easily be a list. 
   # Check to see if it looks "list like"
   elif h_partition_count == 2:
      left_df = horiz_partitions[0]
      left_df["listlike"] = left_df["text"].apply(is_list_like_or_empty)
      if left_df["listlike"].all():
         return "LIST"
      else:
         return "LIST"
   else:
      classification = "TABLE"
   return classification

#########################
### page layout #########
##########################


class LayoutType(str, Enum):
    LEFT_SIDEBAR = "LEFT_SIDEBAR"
    FOOTER = "FOOTER"
    HEADER = "HEADER"
    SIDEBAR = "SIDEBAR"
    BODY = "BODY"

    def __str__(self):
        return str(self.value)

def calculate_area_percentage(words_df, bounds):
  x0, x1, y0, y1 = bounds

  # Assume none of the elements overlap
  total_area = (x1 - x0) * (y1 - y0)

  # Calculate the areas of each of the words_df
  words_df["area"] = (words_df["x1"] - words_df["x0"]) * (words_df["bottom"] - words_df["top"])
  words_area = words_df["area"].sum()

  return words_area / total_area


def estimate_page_layout(words_df, page_props):
  page_layout_elements = {}
  page_layout_types = []
  PAGE_HEIGHT = page_props.get("height")

  # Some general assumptions
  TOP_MARGIN = 72 # 1 inch
  BOTTOM_MARGIN = 72 # 1 inch

  # First, check for a header/footer ------------------
  header_elements = words_df[ words_df["top"] < TOP_MARGIN ]
  footer_elements = words_df[ words_df["top"] > (PAGE_HEIGHT - BOTTOM_MARGIN) ]
  if len(header_elements) > 0:
    page_layout_types.append( LayoutType.HEADER )
  if len(footer_elements) > 0:
    page_layout_types.append( LayoutType.FOOTER )
  
  # Add to our elements
  page_layout_elements[LayoutType.HEADER] = header_elements
  page_layout_elements[LayoutType.FOOTER] = footer_elements

  # Next, check for a left sidebar -----------------
  page_elements = words_df[ (words_df["top"] >= TOP_MARGIN) & (words_df["top"] <= (PAGE_HEIGHT - BOTTOM_MARGIN)) ]
  
  # Get the left/right margins
  left_margin = page_elements["x0"].min()
  right_margin = page_elements["x1"].max()

  # Find the best seam
  best_vertical_seam_x0, left_df, right_df = find_vertical_seam(page_elements)
  print("Best vertical seam: ", best_vertical_seam_x0)

  # If the best seam is the left or right margin, then ignore it
  SIDEBAR_BUFFER = 72
  if (best_vertical_seam_x0 > left_margin + SIDEBAR_BUFFER) & (best_vertical_seam_x0 < right_margin - SIDEBAR_BUFFER):
    
    # If the left side-bar takes up < 30% of the page column, and the right part takes up > ~40% of page, then consider a sidebar
    left_word_area = calculate_area_percentage(left_df, (left_margin, best_vertical_seam_x0, TOP_MARGIN, PAGE_HEIGHT - BOTTOM_MARGIN))
    right_word_area = calculate_area_percentage(right_df, (best_vertical_seam_x0, right_margin, TOP_MARGIN, PAGE_HEIGHT - BOTTOM_MARGIN))

    print(f"Left area: {left_word_area}")
    print(f"Right area: {right_word_area}")

    left_sidebar_width_percent = (best_vertical_seam_x0 - left_margin) / (right_margin - left_margin)

    if left_word_area < 0.3 and left_sidebar_width_percent < 0.5: # and right_word_area > 0.4: # TODO
      page_layout_types.append( LayoutType.LEFT_SIDEBAR )
      page_layout_elements[LayoutType.SIDEBAR] = left_df
      page_layout_elements[LayoutType.BODY] = right_df
      page_props["VERTICAL SEAM"] = best_vertical_seam_x0
    else:
      page_layout_types.append( LayoutType.BODY )
      page_layout_elements[LayoutType.BODY] = page_elements
  else:
    page_layout_types.append( LayoutType.BODY )
    page_layout_elements[LayoutType.BODY] = page_elements

  page_props["LAYOUT TYPES"] = page_layout_types

  return page_layout_elements
  

def partition_page_based_on_layout(layout, words_df):
  right_df = pd.DataFrame()
  left_df = pd.DataFrame()

  if layout == LayoutType.LEFT_SIDEBAR:
    vertical_seam, left_df, right_df = find_vertical_seam(words_df)
  elif layout == LayoutType.FOOTER:
    BOTTOM_MARGIN = 72
    PAGE_HEIGHT = 72*11 # TODO
    horiz_seam = PAGE_HEIGHT - BOTTOM_MARGIN
    right_df = words_df[ words_df["top"] >= horiz_seam ]  # footer
    left_df = words_df[ words_df["top"] < horiz_seam ] 

  return [left_df, right_df]
    

def find_vertical_seam(words_df):
  TOLERANCE = 1.5
  max_count = 0
  best_x0 = 0.

  # First, find the partitions
  h_partitions = find_partitions(words_df, "vertical", 1)

  # Try each of the x-coords (i.e. first element of the tuples)
  # Ignore the first tuple. Determine which one is "best" by which one intersects the most items (i.e. has most left-aligned elements)
  # (Note: another way to do this is to look at total area of the elements)
  for df in h_partitions:
    x0_min = df["x0"].min()
    intersecting_elements_count = len( df[ (df["x0"] > x0_min-TOLERANCE) & (df["x0"] < x0_min+TOLERANCE) ])

    #print("-----")
    #display(df)
    #print("x0 min: ", x0_min)
    #print("COUNT: ", intersecting_elements_count)

    # we're moving left-to-right, so only consider vertical cuts that
    # have a GREATER count
    if intersecting_elements_count > max_count:
      max_count = intersecting_elements_count
      best_x0 = x0_min

  # Given this "best x0", now return the words_df partitioned into these two seams
  left_df = words_df[ words_df["x0"] < best_x0-TOLERANCE ]
  right_df = words_df[ words_df["x0"] >= best_x0-TOLERANCE ]
  
  return best_x0, left_df, right_df

##########################
### PRINTING FUNCTIONS ###
##########################

def print_partitions(partitions):
   """
   Prints the partitions (as returned by "partition_words") to screen.
   """
   for doc_partition in partitions:
      classification = doc_partition.classification
      display_object = doc_partition.display_object
      props = doc_partition.props
      words_df = doc_partition.words_df
      warnings = doc_partition.warnings
      
      # Text
      if (classification == "TEXT") or (classification == "FOOTER") or (classification == "HEADER"):
         text = display_object
         print(f"\nTEXT (size: { props.get('text_height') }) >> {text}")
         if warnings:
            print("Warnings")
            pprint.pprint(warnings)
   
      elif classification == "TABLE":
        print("\nTABLE>>")
        pd.set_option("display.max_rows", None)
        pd.set_option("display.max_columns", None)
        print(pd.DataFrame(display_object).to_markdown(index=False))
        print(f"\n props: col_widths = {props.get('col_widths')}")
        if warnings:
            print("Warnings")
            pprint.pprint(warnings)

      

###################################
# TEXT PARSING
###################################

def concatenate_strings(str1, str2, delim=" "):
   return str1 + (delim + str2 if str1 else str2)

def melt_text_rows_together(words_df, classification):

   # We want to "melt" rows together first, then columns. 

   # One way to do this (and the initial implementation) was to sort the df by "top" then "x0", but this
   # is a little imperfect, because sometimes two "tops" can be off by a tiny bit.

   # Instead, just use our "partition" function to find the rows, then sort the rows by x0.
   margin = 1
   vertical_partitions = find_partitions(words_df, "horizontal", min_margin_height=margin)

   left_boundary = float(np.inf)
   right_boundary = 0
   # Get the bounds of the current text
   for v_part_df in vertical_partitions:
      left_boundary = min(left_boundary, v_part_df["x0"].min())
      right_boundary = max(right_boundary,  v_part_df["x1"].max())

   returned_chunks = []
   final_text = ""
   grouped_df_indexes = []
   current_height = 0
   is_row_header = False
   previous_row_is_header = False
   previous_is_bold, previous_is_italics, styles_match = None, None, False

   for i, v_part_df in enumerate(vertical_partitions): 
      

      # Now that we're going row-by-row: sort by x0, then join with a space
      v_part_df = v_part_df.sort_values(by=["x0"])
      #pprint.pprint(v_part_df)
      
      # Check that everything has the same height
      this_height = v_part_df.at[0,"height"] # TODO: this makes a strong assumption that the first col is the height for the whole thing
      
      # Check to see if EVERYTHING in the line is bold
      is_bold = v_part_df["is_bold"].all()
      is_italic = v_part_df["is_italic"].all()

      # Create the text (and only add in the bold/italics if the whole thing isn't bold/italics)
      if not is_bold and not is_italic:
         v_part_df["formatted_text"] = np.where(
            v_part_df["is_bold"],
            "**" + v_part_df["text"] + "**",
            v_part_df["text"]
         )
         v_part_df["formatted_text"] = np.where(
            v_part_df["is_italic"],
            "*" + v_part_df["formatted_text"] + "*",
            v_part_df["formatted_text"]
         )
      else:
         v_part_df["formatted_text"] = v_part_df["text"]
      v_part_text = " ".join( v_part_df["formatted_text"].astype(str) )


      # Check 1: Does the heights match?
      do_heights_match = is_within_tolerance(current_height, this_height, get_height_tolerance())
      # Check 2: is the current height not yet set?
      is_current_height_not_set = ( current_height == 0 )
      # Check 3: Does the row start with a tab?
      row_starts_with_a_tab = (v_part_df["x0"].min() > left_boundary + get_min_tab_space_width(this_height))
      # Check 4: Is the line a header?
      # This one is probably a bit more imprecise ... let's check 
      #  (1) row ends less than an inch or 80% (whichever is less) and (2) doesn't end in a period
      section_width = right_boundary - left_boundary
      is_row_header = ((v_part_df["x1"].max() < (section_width * .8)) 
                              & (section_width > 72*3) 
                              & (not v_part_df.iloc[-1]["text"].endswith(".")) )
      # Check 5: Are they similarly bolded/italicized?
      if(previous_is_bold == is_bold) & (previous_is_italics == is_italic):
         styles_match = True
      
      # If [the heights are the same (or it's the first row)] AND it's not the last row, mush them together 
      # # TODO: this is kinda ugly logic
      if is_current_height_not_set or (do_heights_match and not row_starts_with_a_tab and not is_row_header
                                       and not previous_row_is_header and styles_match):
         final_text = concatenate_strings(final_text, v_part_text)
         grouped_df_indexes.append(i)
         if current_height == 0:
            current_height = this_height 

      # Otherwise, close out the old row, and create a new one
      else:
         # Close out the prior row
         grouped_dfs = [ vertical_partitions[j] for j in grouped_df_indexes ]
         combined_df = pd.concat(grouped_dfs)
         """
         melted_rows = {
            "text": final_text, 
            "x0": combined_df["x0"].min(),
            "x1": combined_df["x1"].max(),
            "top": combined_df["top"].min(),
            "bottom": combined_df["bottom"].max(),
            "height": combined_df["bottom"].max() - combined_df["top"].min(),
            "direction": combined_df["direction"].dropna().unique().tolist(), # TODO: this should be unique
         }
         melted_df = pd.DataFrame(melted_rows)
         """

         melted_df = combined_df # TODO:
         text_props = {"text_height": current_height, "is_bold": previous_is_bold, "is_italic": previous_is_italics}
         returned_chunks.append( DocPartition(classification, final_text, text_props, melted_df, []) ) # TODO: add warnings if there are any
         
         # Reset
         grouped_df_indexes = []
         grouped_df_indexes.append(i)
         final_text = v_part_text
         current_height = this_height
      
      # Ensure these are set
      previous_is_bold = is_bold
      previous_is_italics = is_italic
      previous_row_is_header = is_row_header
         
         
   
   # TODO: this is a dupe of the above
   if grouped_df_indexes:
         grouped_dfs = [ vertical_partitions[j] for j in grouped_df_indexes ]
         combined_df = pd.concat(grouped_dfs)
         """
         melted_rows = {
            "text": final_text, 
            "x0": combined_df["x0"].min(),
            "x1": combined_df["x1"].max(),
            "top": combined_df["top"].min(),
            "bottom": combined_df["bottom"].max(),
            "height": combined_df["bottom"].max() - combined_df["top"].min(),
            "direction": combined_df["direction"].dropna().unique().tolist() # TODO: this should be unique
         }

         melted_df = pd.DataFrame(melted_rows)
         """
         melted_df = combined_df # TODO:
         text_props = {"text_height": current_height}
         text_props = {"text_height": current_height, "is_bold": previous_is_bold, "is_italic": previous_is_italics}
         returned_chunks.append( DocPartition(classification, final_text, text_props, melted_df, []) ) # TODO: add warnings if there are any
   return returned_chunks
    

###################################
# TABLE PARSING
###################################

def get_tuples_for_partition(partition, partition_type):
   tuples = []
   if partition_type == "vertical":
    start_col = "x0"
    end_col = "x1"
   elif partition_type == "horizontal":
    start_col = "top"
    end_col = "bottom"
   for df in partition:
      tuples.append( (df[start_col].min(), df[end_col].max()) )
   return tuples


def do_col_widths_get_along(cols1, cols2):
   """
   CHecks to see if the two lists of col_widths have columns that overlap more than 1 column in the other list
   """
   # NOTE: this is likely not the most efficient way to do this.  
   # Base case
   if not cols1 or not cols2:
      return False
   
   # Loop through the first set of cols
   for col_widths in cols1:
      x0, x1 = col_widths
      overlap_count = count_number_of_overlaps(x0, x1, cols2)
      if overlap_count > 1:
         print(f" XX {x0}, {x1}, {cols2} --> {overlap_count}")
         return False
      
   # Check the other one (e.g one could have 3 cols, and the other could have 1 col that encompasses all 3)
   for col_widths in cols2:
      x0, x1 = col_widths
      overlap_count = count_number_of_overlaps(x0, x1, cols1)
      if overlap_count > 1:
         return False
   
   # If we got this far, then they play well together
   return True
      
def is_col_widths_subset_of_another(parent_col_widths, child_col_widths):
   for col_widths in child_col_widths:
      x0, x1 = col_widths
      overlap_count = count_number_of_overlaps(x0, x1, parent_col_widths)
      if overlap_count > 1:
         return False
   return True


def compress_intervals(intervals, gap=2):
    compressed = []
    start = intervals[0][0]
    for i, (orig_start, orig_end) in enumerate(intervals):
        width = orig_end - orig_start
        end = start + width
        compressed.append((start, end))
        start = end + gap  # next interval starts after current + gap
    return compressed

def merge_col_widths(parent_col_widths, child_col_widths):
   final_col_widths = []
   
   # Now, loop through the parent col widths, and figure out which ones weren't already picked up
   for tuple in parent_col_widths:
      x0, x1 = tuple
      overlapping_segments = get_overlapping_segments(x0, x1, child_col_widths)
      if len(overlapping_segments) > 1:
         final_col_widths.extend(overlapping_segments) #TODO: compress these intervals smartly
         # compressed_intervals = compress_intervals(overlapping_segments)
      else:
         final_col_widths.append(tuple)

   return sorted(final_col_widths, key=lambda x: x[0])

def count_number_of_overlaps(x0, x1, widths):
   """
   Helper function. counts the number of "width" tuples that overlap with x0/x1
   """
   new_widths = []

   count = 0
   for width in widths:
      width_x0, width_x1 = width

      # THey overlap
      if (x1 > width_x0) & (x0 < width_x1):
         count += 1

   return count #, new_widths

def get_overlapping_segments(x0, x1, widths):
   overlapping_widths = []

   count = 0
   for width in widths:
      width_x0, width_x1 = width

      # THey overlap
      if (x1 > width_x0) & (x0 < width_x1):
         count += 1
         overlapping_widths.append( width ) 

   return overlapping_widths


def parse_list_BAD(words_df, margin_width=1):
   """
   Parsing a list is pretty table-like.

   We already know there are two columns, a small left one and a larger right one.
   """
   returned_partitions = []
   warnings = []

   # What I think is a clever approach: take the HORIZONTAL partitions first, to get the horizontal widths
   #TODO: We calculated this already in classify_chunk, and we know this results in two columns
   margin_height = 8 
   horiz_partitions = find_partitions( words_df, "vertical", min_margin_height=margin_height)

   # Find out the intervals of the list-like elements (bullet points, etc.)
   left_df = horiz_partitions[0]
   right_df = horiz_partitions[1]

   print(">LEFT")
   print(left_df)
   print(">RIGHT")
   print(right_df)

   BULLET_MARGIN = 2
   bullet_partitions = find_partitions(left_df, "horizontal", min_margin_height=BULLET_MARGIN)    

   # Loop through each bullet, and "select" all of the right_df elements within the top/bottom range
   number_of_bullets = len(bullet_partitions)
   print(f"Parsing list, found {number_of_bullets} bullets")

   for ix, v_part_df in enumerate(bullet_partitions):
      top = v_part_df.at[0, "top"] # TODO: Assumes only one element

      # If this is not the last bullet, then get the "bottom" from the next element
      if ix < (number_of_bullets - 1):
         bottom = bullet_partitions[ix+1].at[0, "top"] 
      else:
         bottom = 99999.9 # TODO

      print(f">>>Index {ix}: top {top} and bottom {bottom}")
      print("LEFT SIDE")
      print(v_part_df)

      # Now select everything in right_df
      matching_rows_df = right_df[(right_df["top"] > top) & (right_df["bottom"] < bottom)  ]

      print("MATCHING")
      print(v_part_df)
      if len(matching_rows_df) > 0:
         melted_partitions = melt_text_rows_together(matching_rows_df, "LIST")
         returned_partitions += melted_partitions

   # TODO: add in the list elements, tidy/refactor this all
   return returned_partitions


def parse_list(words_df, margin_width=1): #TODO: make this more variable??
   warnings = []

   # What I think is a clever approach: take the HORIZONTAL partitions first, to get the horizontal widths
   h_widths = determine_col_widths_for_table( words_df )

   # Next, go row by row and build the table
   vert_partitions = find_partitions( words_df, "horizontal", min_margin_height=margin_width)

   table = []
   for v_partition_df in vert_partitions:
      
      row = []
      for horiz_width in h_widths:
         x0, x1 = horiz_width

         # Find all of the rows that match to this column
         matching_rows = v_partition_df[ (v_partition_df["x1"] >= x0) & (v_partition_df["x0"] <= x1) ]
         if len(matching_rows) > 1:
            # If the x0s/x1s are not mutually exclusive (i.e. aren't two separate columns entirely), 
            # then glue the rows together
            overlaps = does_chunk_have_multiple_columns_in_a_row(matching_rows)
            if len(overlaps) > 0:
                warnings.append( ("OVERLAPPING ELEMENTS", 
                                  f"""When parsing the table, muptiple elements were found in the same row and were merged together: '{" ".join(matching_rows["text"].astype(str))}'""")
                )
         
         # Handle bold/italics
         is_bold = matching_rows["is_bold"].all()
         is_italic = matching_rows["is_italic"].all()
         text = " ".join(matching_rows["text"].astype(str))
         if text:
            if is_bold and is_italic:
                text = "***" + text + "***"
            elif is_bold:
                text = "**" + text + "**"
            elif is_italic:
                text = "*" + text + "*"
         row.append(text)
      table.append(row)
   
   table_props = {
      "col_widths": h_widths
   }

   return [ DocPartition( "TABLE", pd.DataFrame(table) , table_props, words_df, warnings )]

def parse_table(words_df, margin_width=1): #TODO: make this more variable??
   warnings = []

   # What I think is a clever approach: take the HORIZONTAL partitions first, to get the horizontal widths
   h_widths = determine_col_widths_for_table( words_df )

   # Next, go row by row and build the table
   vert_partitions = find_partitions( words_df, "horizontal", min_margin_height=margin_width)

   table = []
   for v_partition_df in vert_partitions:
      
      row = []
      for horiz_width in h_widths:
         x0, x1 = horiz_width

         # Find all of the rows that match to this column
         #matching_rows = v_partition_df[ (v_partition_df["x0"] >= x0) & (v_partition_df["x1"] <= x1) ]
         matching_rows = v_partition_df[ (v_partition_df["x1"] >= x0) & (v_partition_df["x0"] <= x1) ]
         if len(matching_rows) > 1:
            # If the x0s/x1s are not mutually exclusive (i.e. aren't two separate columns entirely), 
            # then glue the rows together
            overlaps = does_chunk_have_multiple_columns_in_a_row(matching_rows)
            if len(overlaps) > 0:
                warnings.append( ("OVERLAPPING ELEMENTS", 
                                  f"""When parsing the table, muptiple elements were found in the same row and were merged together: '{" ".join(matching_rows["text"].astype(str))}'""")
                )
         
         # Handle bold/italics
         is_bold = matching_rows["is_bold"].all()
         is_italic = matching_rows["is_italic"].all()
         text = " ".join(matching_rows["text"].astype(str))
         if text:
            if is_bold and is_italic: # TODO: fix this
                text = "***" + text + "***"
            elif is_bold:
                text = "**" + text + "**"
            elif is_italic:
                text = "*" + text + "*"
         row.append(text)
      table.append(row)
   
   table_props = {
      "col_widths": h_widths
   }

   # If there are only (a) two columns and (b) the left column is list-like, then it's actually a list!
   if len(h_widths) == 2:
      print("Assessing if it's a list ... ")
      table_df = pd.DataFrame(table)
      table_df["listlike"] = table_df.iloc[:,0].apply(is_list_like_or_empty) #TOOD: account for bolding
      print(table_df)

      if table_df["listlike"].all():
         final_bullet_list = []
         built_bullet_text = ""
         bullet = ""

         for _, row in table_df.iterrows():
            this_bullet = row.iloc[0]
            this_bullet_text = row.iloc[1]

            # If we encounter a bullet (or it's the first line), then save off the text
            if this_bullet:
               if built_bullet_text:
                  final_bullet_list.append( (bullet, built_bullet_text) )
               bullet = this_bullet
               built_bullet_text = this_bullet_text
            else:
               built_bullet_text += this_bullet_text
         
         # Closing
         if built_bullet_text:
                  final_bullet_list.append( (bullet, built_bullet_text) )

         return [ DocPartition( "LIST", final_bullet_list , {}, words_df, {} )]

   return [ DocPartition( "TABLE", pd.DataFrame(table) , table_props, words_df, warnings )]
   

def determine_col_widths_for_table(words_df):
   # Fist, go row by row, as in "does chunk have multiple columns in a row"
   
   # CHeck to see if there are ... disagreements using the original col_widths
   # TODO: loop through all rows, then check to see if there are more granular col_widths
   # IF there are ... then try to identify the cell that can/should be split

   # First, figure out what the column widths would be for the whole table
   margin_width = 1
   horiz_partitions = find_partitions( words_df, "vertical", min_margin_height=margin_width)
   overall_h_widths = get_tuples_for_partition(horiz_partitions, "vertical")

   # Try just using the last line of the table. Are its columns a subset of the overall ones?
   v_parts = find_partitions( words_df, "horizontal", min_margin_height=margin_width)
   last_v_part_df = v_parts[-1]
   last_row_col_widths = find_partitions( last_v_part_df, "vertical", min_margin_height=margin_width)
   last_row_h_widths = get_tuples_for_partition(last_row_col_widths, "vertical")

   # If it is a subset, then try it out on the whole table. If it fits, return it
   if is_col_widths_subset_of_another(overall_h_widths, last_row_h_widths):
      if do_column_widths_fit_table( words_df, last_row_h_widths ):
         #print(f"Merging {overall_h_widths} and")
         #print(f"        {last_row_h_widths}")
         return merge_col_widths(overall_h_widths, last_row_h_widths)
   
   # Otherwise, fall back to overall table widths
   return overall_h_widths


def do_column_widths_fit_table(words_df, proposed_col_widths, margin_tolerance=1):
    # First, partition the matches by row. This should likely use a tigher tolerance than above.
    v_partitions = find_partitions(words_df, "horizontal", margin_tolerance)
    for v_part_df in v_partitions:
       h_partitions = find_partitions(v_part_df, "vertical", margin_tolerance)
       this_col_width = get_tuples_for_partition(h_partitions, "vertical")

       # Check: is the PROPOSED col widths a subset of this row?
       if is_col_widths_subset_of_another(this_col_width, proposed_col_widths):
          continue
       
       return False
    return True

# TODO: review this
def does_chunk_have_multiple_columns_in_a_row(matches_df, margin_tolerance=1):
    overlaps = []

    # First, partition the matches by row. This should likely use a tigher tolerance than above.
    v_partitions = find_partitions(matches_df, "horizontal", margin_tolerance)

    # Next, partition each sub-partition by column. Check to see if we have multiple "things" in the same line.
    # If we do hae more than 1 , then we have "overlaps"
    for v_part_df in v_partitions:
       h_partitions = find_partitions(v_part_df, "vertical", margin_tolerance)
       if len(h_partitions) > 1:
          overlaps.append( get_tuples_for_partition(h_partitions, "vertical") )
    
    return overlaps


#display(grouped_words

# TODO: add horizontal partition and recursion

# Determine if groups are text, tables, or something else

#display(words_by_row)
#display(row_partition_y_coords)

##################################
###"basic" file reads #############
###################################
def enrich_words_with_style(words, chars):
    enriched_words = []

    for word in words:
        # Find chars within this word's bounding box
        chars_in_word = [
            c for c in chars
            if c["x0"] >= word["x0"] and c["x1"] <= word["x1"] and
               c["top"] >= word["top"] and c["bottom"] <= word["bottom"]
        ]
        fontnames = [c["fontname"] for c in chars_in_word]
        most_common_font = Counter(fontnames).most_common(1)
        font = most_common_font[0][0] if most_common_font else None

        enriched_words.append({
            **word,
            "fontname": font,
            "is_bold": "Bold" in font if font else False,
            "is_italic": any(k in font for k in ["Italic", "Oblique"]) if font else False
        })

    return enriched_words

def read_pdf_pages_from_filepath(filepath, pages, words_x_tolerance=1):
  page_props = {}

  with pdfplumber.open(filepath) as pdf:
      page = pdf.pages[pages - 1] # account for 0-index

      text = page.extract_text()
      #print(text)

      words = page.extract_words(x_tolerance = words_x_tolerance, extra_attrs=["fontname"])
      words = enrich_words_with_style(words, page.chars)
      #display(words)

      tables = page.extract_table() # table_settings={"vertical_strategy": "text", "horizontal_strategy": "text"})
      #print(tables

      # Set the properties
      page_props["width"] = page.width
      page_props["height"] = page.height

      #p0 = page.to_image(resolution=150)
      im = page.to_image()
      im.draw_rects(words)

      #df = pd.DataFrame(table[1:], columns=table[0])
  return text, words, page_props




def display_page_chunks(page_chunks):
   for words_by_row in page_chunks:
      print("===================================")
      display_word_groups(words_by_row)

def display_word_groups(words_by_row):
    for top, top_vals in words_by_row.items():
       print(f"Y = {top}---------------")
       for left, left_vals in top_vals.items():
          text = left_vals.get("text", "")
          height = left_vals.get("height", "")
          x0 = left_vals.get("x0", "")
          x1 = left_vals.get("x1", "")
          
          print(f"  X ={str(left).rjust(6)} | '{text}'    | height: {height} | Ymax: {top+height} | X: [{x0}, {x1}]")


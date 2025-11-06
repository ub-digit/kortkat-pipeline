import json
import pandas as pd
import argparse
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import classification_report
from matplotlib.backends.backend_pdf import PdfPages
import array as arr
from datetime import datetime

# TODO Document the required format of the match results and ground truth files


def load_data(match_results_path, ground_truth_path):

    matchresults_df = None
    gt_df = None
    
    # Load match results
    if match_results_path.suffix.lower() not in [".xlsx", ".xls"]:
        raise ValueError(f"Ground truth file must be an Excel file")
    else:
        try:
            matchresults_df = pd.read_excel(match_results_path, dtype={"box": object, "card": object})
            print(f"Loaded match results from {match_results_path}")
        except Exception as e:
            print(f"  Error loading {match_results_path}: {e}")        
    
    # Load ground trouth
    if ground_truth_path.suffix.lower() not in [".xlsx", ".xls"]:
        raise ValueError(f"Ground truth file must be an Excel file")
    else:
        try:
            gt_df = pd.read_excel(ground_truth_path, dtype={"box": object, "card": object})
            print(f"Loaded ground truth data from {ground_truth_path}")
        except Exception as e:
            print(f"  Error loading {ground_truth_path}: {e}")
        

    if matchresults_df is not None and not matchresults_df.empty and gt_df is not None and not gt_df.empty:

        initial_count_of_match_objects = matchresults_df['match_object_ID'].nunique()
        initial_count_of_cards_from_match = matchresults_df['card_ID'].nunique()
        print(f"- Initial number of match objects: {initial_count_of_match_objects} (from {initial_count_of_cards_from_match} cards)")
        
        initial_count_of_gt_entries = gt_df['gt_entry_ID'].nunique()
        initial_count_of_cards_from_gt = gt_df['card_ID'].nunique() 
        print(f"- Initial number of ground truth entries: {initial_count_of_gt_entries} (from {initial_count_of_cards_from_gt} cards)")

        # Count the number of unique "Hänvisning" card types in match results
        number_of_reference_match_objects = matchresults_df[matchresults_df["card_type"] == "Hänvisning"]["match_object_ID"].nunique()
        
        # Remove "Hänvisning" card type from match results
        matchresults_without_references_df = matchresults_df[matchresults_df["card_type"] != "Hänvisning"]
        print(f"- Ignoring {number_of_reference_match_objects} match objects where card type is \"Hänvisning\"")        

        # Count unique match_object_ids per card_id        
        match_objects_per_card_from_match = matchresults_without_references_df.groupby('card_ID')['match_object_ID'].nunique().reset_index()
        match_objects_per_card_from_match.rename(columns={'match_object_ID': 'unique_match_objects'}, inplace=True)

        match_objects_per_card_from_gt = gt_df.groupby('card_ID')['gt_entry_ID'].nunique().reset_index()
        match_objects_per_card_from_gt.rename(columns={'gt_entry_ID': 'unique_gt_entries'}, inplace=True)

        # Find card_ids where the unique match counts are equal
        matching_cards = pd.merge(match_objects_per_card_from_match, match_objects_per_card_from_gt, on='card_ID', how='inner')
        matching_cards = matching_cards[matching_cards['unique_match_objects'] == matching_cards['unique_gt_entries']]        

        # Filter the original dataframes to only include the matching card_ids
        matchresults_without_references_filtered_df = matchresults_without_references_df[matchresults_without_references_df['card_ID'].isin(matching_cards['card_ID'])]
        gt_filtered_df = gt_df[gt_df['card_ID'].isin(matching_cards['card_ID'])]

        count_of_match_objects_without_references = matchresults_without_references_df['match_object_ID'].nunique()
        remaining_count_of_match_objects = matchresults_without_references_filtered_df['match_object_ID'].nunique()
        remaining_count_of_gt_entries = gt_filtered_df['gt_entry_ID'].nunique()

        removed_count_of_match_objects = count_of_match_objects_without_references - remaining_count_of_match_objects
        removed_count_of_gt_entries = initial_count_of_gt_entries - remaining_count_of_gt_entries
        print(f"- Removed {removed_count_of_match_objects} match objects from cards where the number of match objects did not equal the number of ground truth entries")
        print(f"- Removed {removed_count_of_gt_entries} ground truth entries from cards that where removed from the match results")

        # Merge match results with ground truth data
        merged_df = matchresults_without_references_filtered_df.merge(gt_filtered_df, how="inner", left_on="match_object_ID", right_on="gt_entry_ID", suffixes=(None, "_gt"))        
        
    else:        
        print("No match results or ground truth data found.")
        return None, None, None

    return matchresults_df, gt_df, merged_df


def evaluate_extracted_card_types(matchresults_df, gt_df):
    
    filtered_matchresults_df = matchresults_df[["card_ID", "card_type"]].drop_duplicates(keep="first")
    filtered_gt_df = gt_df[["card_ID", "gt_card_type"]].drop_duplicates(keep="first")

    merged_card_types_df = filtered_matchresults_df.merge(filtered_gt_df, how="outer", on="card_ID", suffixes=(None, "_gt"))
    merged_card_types_df["card_type"] = merged_card_types_df["card_type"].fillna("Unknown")
    merged_card_types_df["gt_card_type"] = merged_card_types_df["gt_card_type"].fillna("Unknown")

    return merged_card_types_df


def evaluate_extracted_occurences(matchresults_df, gt_df):
    # Create set of unique cards that have gone through the matching process and are not "Hänvisning"
    cards_df = matchresults_df[matchresults_df["card_type"] != "Hänvisning"][["card_ID"]].drop_duplicates(keep="first")
    
    # Remove match objects of type "No edition" and duplicate match objects (e.g. multiple matches)
    matchresults_df = matchresults_df[matchresults_df["match_stat"] != "No edition"].drop_duplicates(subset="match_object_ID", keep="first")
    
    # Count the number of match objects per card
    count_of_matchobjects_per_card = matchresults_df["card_ID"].value_counts().rename("match_count")
    
    # Count the number of ground truth entries per card
    count_of_gt_entries_per_card = gt_df["card_ID"].value_counts().rename("gt_count")

    # Join the counts to the cards DataFrame
    counts_df = cards_df.set_index('card_ID').join(count_of_matchobjects_per_card, how='left').join(count_of_gt_entries_per_card, how='left').fillna(0).astype(int).reset_index()

    return counts_df

    
def evaluate_matches(matches_df, output_directory, job_name):
    
    # Evaluate if the matched ID is in the libris_ID
    matches_df['match_result'] = matches_df.apply(evaluate_match, axis=1)    
    
    correct_single_matches = matches_df[(matches_df["match_result"] == "Correct") & (matches_df["match_stat"] == "Single")]
    incorrect_single_matches = matches_df[(matches_df["match_result"] == "Incorrect") & (matches_df["match_stat"] == "Single")]
    
    correct_multiple_matches = matches_df[(matches_df["match_result"] == "Correct") & (matches_df["match_stat"] == "Multiple")]
    incorrect_multiple_matches = matches_df[matches_df["match_stat"] == "Multiple"].groupby("match_object_ID").filter(lambda g: (g["match_result"] != "Correct").all())
    
    correct_unqualified_single_matches = matches_df[(matches_df["match_result"] == "Correct") & (matches_df["match_stat"] == "Unqualified")]
    incorrect_unqualified_single_matches = matches_df[(matches_df["match_result"] == "Incorrect") & (matches_df["match_stat"] == "Unqualified")]
    
    correct_unqualified_multiple_matches = matches_df[(matches_df["match_result"] == "Correct") & (matches_df["match_stat"] == "Unqualified multiple")]
    incorrect_unqualified_multiple_matches = matches_df[matches_df["match_stat"] == "Unqualified multiple"].groupby("match_object_ID").filter(lambda g: (g["match_result"] != "Correct").all())    

    matches_similarity_scores = {
        "single_matches": {
            "title": "Distribution of match candidates - single matches",
            "cumulative_mode": "series",
            "correct": correct_single_matches["similarity"].tolist(),
            "incorrect": incorrect_single_matches["similarity"].tolist()
        },
        "multiple_matches": {
            "title": "Distribution of match candidates - multiple matches",
            "cumulative_mode": "series",
            "correct": correct_multiple_matches["similarity"].tolist(),
            "incorrect": incorrect_multiple_matches["similarity"].tolist()
        },
        "unqualified_single_matches": {
            "title": "Distribution of match candidates - unqualified single matches",
            "cumulative_mode": "series",
            "correct": correct_unqualified_single_matches["similarity"].tolist(),
            "incorrect": incorrect_unqualified_single_matches["similarity"].tolist()
        },
        "unqualified_multiple_matches": {
            "title": "Distribution of match candidates - unqualified multiple matches",
            "cumulative_mode": "series",
            "correct": correct_unqualified_multiple_matches["similarity"].tolist(),
            "incorrect": incorrect_unqualified_multiple_matches["similarity"].tolist()
        }
    }

    # Label each match as correct/incorrect/no edition/top correct
    results_df = matches_df.groupby("match_object_ID").apply(label_matches).reset_index(drop=True)

    # Generate subsets of results for different analyses
    top_correct_single_match_results = results_df[(results_df["result"] == "Correct") & (results_df["match_stat"] == "Single")]
    top_correct_multiple_match_results = results_df[(results_df["result"] == "Correct") & (results_df["match_stat"] == "Multiple")]

    correct_multiple_match_results = results_df[(results_df["result"] == "Secondary correct") & (results_df["match_stat"] == "Multiple")]
    incorrect_multiple_match_results = results_df[(results_df["result"] == "Incorrect") & (results_df["match_stat"] == "Multiple")]
    top_correct_match_results = results_df[(results_df["result"] == "Correct") & (results_df["match_stat"] == "Multiple") | (results_df["result"] == "Correct") & (results_df["match_stat"] == "Single")]
    incorrect_single_match_results = results_df[(results_df["result"] == "Incorrect") & (results_df["match_stat"] == "Single")]

    match_results_similarity_scores = {
        "top_correct_single_matches": {
            "cumulative_mode": "series",
            "title": "Distribution of match results (single) - top correct vs incorrect",
            "correct": top_correct_single_match_results["matched_similarity"].tolist(),
            "incorrect": incorrect_single_match_results["matched_similarity"].tolist()
        },
        "top_correct_multiple_matches": {
            "cumulative_mode": "series",
            "title": "Distribution of match results (multiple) - top correct vs correct + incorrect",
            "correct": top_correct_multiple_match_results["matched_similarity"].tolist(),
            "incorrect": incorrect_multiple_match_results["matched_similarity"].tolist() + correct_multiple_match_results["matched_similarity"].tolist()
        },
        "correct_multiple_matches": {
            "title": "Distribution of match results - correct vs incorrect multiple matches",
            "cumulative_mode": "series",
            "correct": correct_multiple_match_results["matched_similarity"].tolist(),
            "incorrect": incorrect_multiple_match_results["matched_similarity"].tolist()
        }
    }

    total_match_results_similarity_scores = {
        "all": {
            "title": "Distribution of match results (all) - top correct vs correct + incorrect",
            "cumulative_mode": "total",
            "correct": top_correct_match_results["matched_similarity"].tolist(),
            "incorrect": incorrect_multiple_match_results["matched_similarity"].tolist() + incorrect_single_match_results["matched_similarity"].tolist() + correct_multiple_match_results["matched_similarity"].tolist()
        }
    }

    # Match results for mongraphs
    correct_single_match_results_monographs = results_df[(results_df["result"] == "Correct") & (results_df["match_stat"] == "Single") & (results_df["card_type"] == "Monografi")]
    incorrect_single_match_results_monographs = results_df[(results_df["result"] == "Incorrect") & (results_df["match_stat"] == "Single") & (results_df["card_type"] == "Monografi")]
    monographs_match_results_similarity_scores = {
        "single": {
            "cumulative_mode": "total",
            "title": "Distribution of match results (single, monographs) - correct vs incorrect",
            "correct": correct_single_match_results_monographs["matched_similarity"].tolist(),
            "incorrect": incorrect_single_match_results_monographs["matched_similarity"].tolist()
        }
    }

    generate_pdf_report([matches_similarity_scores, match_results_similarity_scores, total_match_results_similarity_scores, monographs_match_results_similarity_scores], output_directory, job_name)

    return matches_df, results_df    


def label_matches(group):

    matched_similarity = None
    matched_ID = None
    correct_count =None

    if (group['match_stat'] == 'No match').any():
        row = group.iloc[0]
        if row['match_result'] == 'Correct':
            result = "Correct"
        else:
            result = "Incorrect"            
    elif (group['match_stat'] == 'No edition').any():
        result = "No edition"
    else:        
        top_candidate = group.loc[group['similarity'].idxmax()].copy()
        correct_count = (group['match_result'] == 'Correct').sum()        
        if top_candidate["match_result"] == "Correct":
            result = "Correct"
            matched_similarity = top_candidate["similarity"]
            matched_ID = top_candidate["matched_ID"]
        elif correct_count > 0:
            group_copy = group.copy()
            candidates_to_keep = group_copy['match_result'] == "Correct"
            group_copy = group_copy[candidates_to_keep]
            top_candidate = group_copy.loc[group_copy['similarity'].idxmax()].copy()
            result = "Secondary correct"
            matched_similarity = top_candidate["similarity"]
            matched_ID = top_candidate["matched_ID"]
        else:
            matched_similarity = top_candidate["similarity"]
            matched_ID = top_candidate["matched_ID"]
            result = "Incorrect"

    results = pd.Series({
        "box": group['box'].iloc[0],
        "card": group['card'].iloc[0],
        "card_ID": group['card_ID'].iloc[0],
        "match_object_ID": group['match_object_ID'].iloc[0],        
        "kortkat_URL": f"https://kortkat.ub.gu.se/card/{group["box"].iloc[0]}/{group["card"].iloc[0]}",        
        "gt_card_type": group['gt_card_type'].iloc[0],
        "gt_truth_type": group['gt_truth_type'].iloc[0],
        "gt_libris_ID": group['libris_ID'].iloc[0],
        "card_type": group['card_type'].iloc[0],
        "match_stat": group['match_stat'].iloc[0],        
        "matched_ID": matched_ID,
        "matched_similarity": matched_similarity,
        "matched_IDs": ", ".join([str(id) if pd.notna(id) else '' for id in group.sort_values(by='similarity', ascending=False)['matched_ID']]),
        "similarity_scores": ", ".join([f"{sim:.4f}" if pd.notna(sim) else '' for sim in group.sort_values(by='similarity', ascending=False)['similarity']]),
        "correct_count": correct_count,
        "result": result
    })

    return results

def parse_gt_id_string(id_string):
    # replace all semicolons with commas
    id_string = str(id_string).replace(";", ",")
    # split the string by commas
    id_list = id_string.split(",")
    # strip whitespace and filter out empty strings
    id_list = [id.strip() for id in id_list if id.strip()]
    return id_list

def evaluate_match(row):
    matched_id = row['matched_ID']
    libris_id = row['libris_ID']
    match_stat = row['match_stat']
    truth_type = row['gt_truth_type']

    if match_stat == "No match":
        if truth_type == "no-match":
            return "Correct"
        else:
            return "Incorrect"
    elif match_stat == "No edition":
        return "No edition"
    else:
        gt_id_list = parse_gt_id_string(libris_id)
        # check if mathed_id is in the list of gt_ids
        if matched_id in gt_id_list:
            return "Correct"
        else:
            return "Incorrect"

def evaluate_card_completeness(match_results):    
    #If result for all match objects for a card is "correct", then the card is complete, else incomplete. Return only unique card_IDs with completeness status.
    completeness_df = match_results.groupby("card_ID").apply(lambda g: pd.Series({
        "box": g["box"].iloc[0],
        "card": g["card"].iloc[0],
        "card_type": g["card_type"].iloc[0],
        "completeness": "Complete" if (g["match_stat"] == "Single").all() else "Incomplete"        
    })).reset_index()
    
    return completeness_df
        
def draw_histogram(data, ax=None):

    correct = np.array(data["correct"]) 
    incorrect = np.array(data["incorrect"])

    # Combine correct and incorrect to find global min and max
    score_min = min(correct.min(), incorrect.min())   
    score_max = max(correct.max(), incorrect.max())
    
    # Add a small buffer for nice axis padding
    score_range = score_max - score_min
    padding = 0.05 * score_range
    bin_min = max(0, score_min - padding)
    bin_max = min(1, score_max + padding)

    # Create bins based on dynamic min/max
    bins = np.linspace(bin_min, bin_max, 40)
    bin_centers = (bins[:-1] + bins[1:]) / 2

    ax.hist(correct, label='Correct', bins=bins, color="green", edgecolor='black', linewidth=0.5)
    ax.hist(incorrect, label='Incorrect', bins=bins, color="red", edgecolor='black', linewidth=0.5, alpha=0.6)
    
    correct_counts, _ = np.histogram(correct, bins=bins)
    incorrect_counts, _ = np.histogram(incorrect, bins=bins)    
    total_counts = correct_counts + incorrect_counts

    ax.set_title(data["title"])
    ax.set_xlabel('Similarity score')
    ax.set_ylabel('Frequency')    

    ax2 = ax.twinx()

    def reverse_cumulative_percent(values, bins, total=None):
        counts, _ = np.histogram(values, bins=bins)
        cumulative = np.cumsum(counts[::-1])[::-1]
        if total is not None:
            return 100 * cumulative / total
        else:
            return 100 * cumulative / cumulative[0]

    total_cumulative = np.cumsum(total_counts[::-1])[::-1]    
    total_cumulative[total_cumulative == 0] = 1
    
    # Plot reverse cumulative lines
    if data["cumulative_mode"] == "total":
        correct_cumulative = reverse_cumulative_percent(correct, bins, total_cumulative[0])
        incorrect_cumulative = reverse_cumulative_percent(incorrect, bins, total_cumulative[0])        
    else:
        correct_cumulative = reverse_cumulative_percent(correct, bins)    
        incorrect_cumulative = reverse_cumulative_percent(incorrect, bins)
    
    
    ax2.plot(bin_centers, correct_cumulative, color='darkgreen', linestyle='-', label='% ≥ score (Correct)')
    ax2.plot(bin_centers, incorrect_cumulative, color='darkred', linestyle='--', label='% ≥ score (Incorrect)')

    ax2.set_ylabel('Cumulative % ≥ score')
    ax2.set_ylim(0, 105)
    ax2.tick_params(axis='y', labelcolor='black')
    ax2.grid(which='both', visible=True, linestyle='--', linewidth=0.5)

def generate_pdf_report(similarity_scores_list, ouptput_directory, job_name):

    ouptput_directory.mkdir(parents=True, exist_ok=True)
    filename = ouptput_directory / str(job_name + "_scores.pdf")

    with PdfPages(filename) as pdf:
        for similarity_scores in similarity_scores_list:
            num_plots = len(similarity_scores.items())
            fig, axs = plt.subplots(num_plots, 1, figsize=(mm_to_inches(210), mm_to_inches(297)))
            
            if num_plots == 1:
                axs = [axs]
            else:
                axs = axs.flatten()

            for (category, scores), ax in zip(similarity_scores.items(), axs):
                draw_histogram(scores, ax)
                plt.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)

def generate_excel_report(evaluated_matches, match_results, evaluated_card_types, evaluated_extracted_occurences, evaluated_card_completeness, settings_path, output_directory, job_name):
    match_evaluation_report_filename = output_directory / str(job_name + "_report.xlsx")

    with pd.ExcelWriter(match_evaluation_report_filename, engine="xlsxwriter") as writer:
        # Write entire matches_df to Excel
        evaluated_matches.to_excel(writer, sheet_name="Matches", index=False)

        # Write results to Excel
        match_results.to_excel(writer, sheet_name="Match results", index=False)
        
        # Write match results statistics to Excel
        match_results_statistics_sheet_name = "Match results statistics"

        all_match_stats = match_results["match_stat"].unique()
        all_results = match_results["result"].unique()

        all_match_stats.sort()
        all_results.sort()

        card_type_filters = ['All'] + match_results['card_type'].unique().tolist()
        box_filters = ['All'] + match_results['box'].unique().tolist()

        row_spacer = 2
        col_spacer = 3

        max_table_height = 0
        max_table_width = 0

        workbook = writer.book
        percent_format = workbook.add_format({'num_format': '0.00%'})

        for card_filter in card_type_filters:
            for box_filter in box_filters:
                df_subset = match_results.copy()
                
                if card_filter != 'All':
                    df_subset = df_subset[df_subset['card_type'] == card_filter]
                
                if box_filter != 'All':
                    df_subset = df_subset[df_subset['box'] == box_filter]

                if not df_subset.empty:
                    pivot_table = df_subset.pivot_table(index="match_stat", columns="result", values="match_object_ID", aggfunc="count", fill_value=0)
                    pivot_table = pivot_table.reindex(index=all_match_stats, columns=all_results, fill_value=0)
                    max_table_height = max(max_table_height, pivot_table.shape[0] + 1)
                    max_table_width = max(max_table_width, pivot_table.shape[1] + 1)

        static_row_step = max_table_height + 1 + row_spacer
        static_col_step = max_table_width + col_spacer

        def calculate_error_rate(row):
            correct = row.get('Correct', 0)
            incorrect = row.get('Incorrect', 0)
            secondary_correct = row.get('Secondary correct', 0)
            total = correct + incorrect + secondary_correct
            if total == 0:
                return np.nan
            else:
                return (incorrect + secondary_correct) / total

        for i, card_filter in enumerate(card_type_filters):
            for j, box_filter in enumerate(box_filters):
                current_start_row = i * static_row_step
                current_start_col = j * static_col_step
                
                df_subset = match_results.copy()
                
                if card_filter != 'All':
                    df_subset = df_subset[df_subset['card_type'] == card_filter]
                
                if box_filter != 'All':
                    df_subset = df_subset[df_subset['box'] == box_filter]

                if not df_subset.empty:
                    pivot_table = df_subset.pivot_table(index="match_stat", columns="result", values="match_object_ID", aggfunc="count", fill_value=0)
                else:
                    pivot_table = pd.DataFrame({'Info': ['No Data']})

                pivot_table = pivot_table.reindex(index=all_match_stats, columns=all_results, fill_value=0)
                pivot_table['Error rate'] = pivot_table.apply(calculate_error_rate, axis=1)             
                                
                # Format error rate as percentage with two decimal places
                # pivot_table['Error rate'] = pivot_table['Error rate'].apply(lambda x: f"{x:.2%}" if pd.notna(x) else 'N/A')                
                
                label_text = f'{card_filter}/{box_filter}'
                label_df = pd.DataFrame([label_text])
                
                label_df.to_excel(writer, sheet_name=match_results_statistics_sheet_name, startrow=current_start_row, startcol=current_start_col, header=False, index=False)                
                pivot_table.to_excel(writer, sheet_name=match_results_statistics_sheet_name, startrow=current_start_row + 1, startcol=current_start_col, header=True, index=True)

                error_rate_column_index = pivot_table.columns.get_loc('Error rate') + 1
                worksheet = writer.sheets[match_results_statistics_sheet_name]
                worksheet.set_column(current_start_col + error_rate_column_index, current_start_col + error_rate_column_index, None, percent_format)
                

        # Write card types confusion matrix to Excel
        card_types_confusion_matrix = evaluated_card_types.pivot_table(index="gt_card_type", columns="card_type", values="card_ID", aggfunc="count", fill_value=0)
        card_types_confusion_matrix.to_excel(writer, sheet_name="Card types confusion matrix", index=True)

        # Write card types classification report to Excel
        card_types_true = evaluated_card_types["gt_card_type"]
        card_types_pred = evaluated_card_types["card_type"]

        card_types_classification_report_dict = classification_report(card_types_true, card_types_pred, zero_division=0, output_dict=True)
        card_types_classification_report_df = pd.DataFrame(card_types_classification_report_dict).transpose()        
        card_types_classification_report_df.to_excel(writer, sheet_name="Card types performance", index=True)

        # Write occurences confusion matrix to Excel
        occurences_confusion_matrix = evaluated_extracted_occurences.pivot_table(index="gt_count", columns="match_count", values="card_ID", aggfunc="count", fill_value=0)
        occurences_confusion_matrix.to_excel(writer, sheet_name="Occurences confusion matrix", index=True)
        
        # Write occurences classification report to Excel
        occurences_true = evaluated_extracted_occurences["gt_count"]
        occurences_pred = evaluated_extracted_occurences["match_count"]
        occurences_classification_report_dict = classification_report(occurences_true, occurences_pred, zero_division=0, output_dict=True)
        occurences_classification_report_df = pd.DataFrame(occurences_classification_report_dict).transpose()        
        occurences_classification_report_df.to_excel(writer, sheet_name="Occurences performance", index=True)

        #Write card completeness to pivot table
        card_completeness_pivot = evaluated_card_completeness.pivot_table(index="card_type", columns="completeness", values="card_ID", aggfunc="count", fill_value=0)
        card_completeness_pivot.to_excel(writer, sheet_name="Card completeness", index=True)

        # Write settings JSON to Excel
        print(f"Writing settings from {settings_path} to Excel")
        if settings_path:
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)

            # Convert the whole JSON to a pretty string
            json_str = json.dumps(settings, indent=2)

            # Create a DataFrame with one row: "Settings" | JSON string
            df = pd.DataFrame([["Settings:", json_str]])

            # Write to a new sheet
            df.to_excel(writer, sheet_name="Extraction and match settings", index=False, header=False)

def mm_to_inches(mm):
    return mm / 25.4

def parse_args():
    parser = argparse.ArgumentParser(description="Validate match run with known structure")

    # Main entry: match run directory (with known filenames)
    parser.add_argument("--match_directory", type=Path, help="Directory containing match run files")

    # Optional overrides
    parser.add_argument("--matches_file", type=Path, help="Path to matches Excel file")
    parser.add_argument("--settings_file", type=Path, help="Path to settings JSON file")

    # Central ground truth file (defaulted)
    parser.add_argument("--ground_truth_file", type=Path, default=Path("./gt.xlsx"), help="Path to ground truth file (default: ./gt.xlsx)")

    # Output directory
    parser.add_argument("--output_directory", type=Path, required=True, help="Directory to write reports to")
    parser.add_argument("--job_name", type=str, default=f"batch-job-{datetime.now().strftime("%Y-%m-%d-%H-%M-%S")}", help="Display name for batch job")

    return parser.parse_args()


def resolve_paths(args):
    # Defaults for known filenames in match run directories
    default_matches_file = "outputfile.xlsx"
    default_settings_file = "outputfile-report.json"

    if args.match_directory:
        match_dir = args.match_directory.resolve()

        matches_path = args.matches_file or (match_dir / default_matches_file)
        settings_path = args.settings_file or (match_dir / default_settings_file)
    else:
        if not args.matches or not args.settings:
            raise ValueError("If --match_directory is not provided, both --matches_file and --settings_file must be set.")
        matches_path = args.matches_file.resolve()
        settings_path = args.settings_file.resolve()

    ground_truth_path = args.ground_truth_file.resolve()
    output_dir = args.output_directory.resolve()

    # Check existence of required input files
    missing = []
    for path, label in [(matches_path, "Matches file"),
                        (settings_path, "Settings file"),
                        (ground_truth_path, "Ground truth file")]:
        if not path.is_file():
            missing.append(f"{label} not found: {path}")
    if missing:
        raise FileNotFoundError("\n".join(missing))

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    return matches_path, settings_path, ground_truth_path, output_dir

if __name__ == "__main__":

    args = parse_args()
    matches_path, settings_path, ground_truth_path, output_dir = resolve_paths(args)

    matchresults_df, gt_df, merged_df = load_data(matches_path, ground_truth_path)

    evaluated_card_types = evaluate_extracted_card_types(matchresults_df, gt_df)
    evaluated_extracted_occurences = evaluate_extracted_occurences(matchresults_df, gt_df)
    
    if merged_df is not None and not merged_df.empty:        
        # evaluated_matches, match_statistics = evaluate_matches(merged_df, output_dir)
        evaluated_matches, match_results = evaluate_matches(merged_df, output_dir, args.job_name)
        evaluated_card_completeness = evaluate_card_completeness(match_results)
        generate_excel_report(evaluated_matches, match_results, evaluated_card_types, evaluated_extracted_occurences, evaluated_card_completeness, settings_path, output_dir, args.job_name)
    else:
        print("No data to evaluate.")

    print("Done. Check the output directory for results.")

    

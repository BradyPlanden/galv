#!/usr/bin/env python

# =========================== MRG Copyright Header ===========================
#
# Copyright (c) 2003-2019 University of Oxford. All rights reserved.
# Authors: Mobile Robotics Group, University of Oxford
#          http://mrg.robots.ox.ac.uk
#
# This file is the property of the University of Oxford.
# Redistribution and use in source and binary forms, with or without
# modification, is not permitted without an explicit licensing agreement
# (research or commercial). No warranty, explicit or implicit, provided.
#
# =========================== MRG Copyright Header ===========================
#
# @author Luke Pitt.
#

import galvanalyser.harvester.battery_exceptions as battery_exceptions
import galvanalyser.harvester.maccor_functions as maccor_functions
import galvanalyser.harvester.ivium_functions as ivium_functions
from itertools import accumulate
import traceback

# see https://gist.github.com/jsheedy/ed81cdf18190183b3b7d
# https://stackoverflow.com/a/30721460


def load_metadata(file_type, file_path):
    """
        Reads metadata contained in the file and
        Identifies which columns are present in the file and which have data
    """
    if "MACCOR" in file_type:
        if "EXCEL" in file_type:
            return maccor_functions.load_metadata_maccor_excel(file_path)
        elif "RAW" in file_type:
            return maccor_functions.load_metadata_maccor_raw(file_path)
        else:
            return maccor_functions.load_metadata_maccor_text(
                file_type, file_path
            )
    elif "IVIUM" in file_type:
        if "TXT" in file_type:
            return ivium_functions.load_metadata_ivium_text(file_path)
    raise battery_exceptions.UnsupportedFileTypeError


def identify_file(file_path):
    """
        Returns a string identifying the type of the input file
    """
    try:
        if file_path.endswith(".xls"):
            return {"EXCEL", "MACCOR"}
        elif file_path.endswith(".xlsx"):
            return {"EXCEL", "MACCOR"}
        elif file_path.endswith(".csv"):
            if maccor_functions.is_maccor_text_file(file_path, ","):
                return {"CSV", "MACCOR"}
            elif maccor_functions.is_maccor_text_file(file_path, "\t"):
                return {"TSV", "MACCOR"}
        elif file_path.endswith(".txt"):
            if file_path.endswith(".mps.txt"):
                # Bio-Logic settings file, doesn't contain data
                pass
            elif file_path.endswith(".mps.txt"):
                # Bio-Logic text data file
                pass
            elif maccor_functions.is_maccor_text_file(file_path, "\t"):
                return {"TSV", "MACCOR"}
            elif ivium_functions.is_ivium_text_file(file_path):
                return {"TXT", "IVIUM"}
        else:
            # No extension or unrecognised extension
            if maccor_functions.is_maccor_raw_file(file_path):
                return {"RAW", "MACCOR"}
    except Exception as ex:
        print("Error identifying file: " + file_path)
        print(ex)
    raise battery_exceptions.UnsupportedFileTypeError


def get_default_sample_time_setep(file_type):
    # TODO handle other file types
    # TODO do something better here
    if "MACCOR" in file_type:
        return 1.0 / 60.0
    else:
        raise battery_exceptions.UnsupportedFileTypeError


class InputFile:
    """
        A class for handling input files
    """

    def __init__(self, file_path):
        self.file_path = file_path
        self.type = identify_file(file_path)
        self.metadata, self.column_info = load_metadata(self.type, file_path)

    def get_file_column_to_standard_column_mapping(self):
        """
            returns map of file column name strings to column id numbers
        """
        if "MACCOR" in self.type:
            print("Type is MACCOR")
            return (
                maccor_functions.get_maccor_column_to_standard_column_mapping()
            )
        elif "IVIUM" in self.type:
            print("Type is IVIUM")
            return (
                ivium_functions.get_ivium_column_to_standard_column_mapping()
            )
        else:
            raise battery_exceptions.UnsupportedFileTypeError

    def get_standard_column_to_file_column_mapping(self):
        file_col_to_std_col = self.get_file_column_to_standard_column_mapping()
        return {
            value: key
            for key, value in file_col_to_std_col.items()
            if value is not None
        }

    def get_names_of_columns_with_data(self):
        return {
            key for key, value in self.column_info.items() if value["has_data"]
        }

    def get_names_of_numeric_columns_with_data(self):
        return {
            key
            for key, value in self.column_info.items()
            if value["has_data"] and value["is_numeric"]
        }

    def get_unknown_numeric_columns_with_data_names(
        self, standard_cols_to_file_cols=None
    ):
        if standard_cols_to_file_cols is None:
            standard_cols_to_file_cols = {}
        known_map = self.get_file_column_to_standard_column_mapping()
        columns_with_data = self.get_names_of_numeric_columns_with_data()
        return columns_with_data - (
            set(known_map.keys()) | set(standard_cols_to_file_cols.values())
        )

    def get_test_start_date(self):
        # TODO look check file type, ask specific implementation for metadata value
        return self.metadata["Date of Test"]

    def complete_columns(
        self, required_column_ids, file_cols_to_data_generator,
        last_values=None
    ):
        """
            Generates missing columns, returns generator of lists that match
            required_column_ids
        """
        flag = True
        rec_col_set = set(required_column_ids)
        existing_values = {}
        if last_values is not None:
            existing_values = {tsdr.column_id: tsdr.value for tsdr in last_values.items()}
            if 0 not in existing_values:
                existing_values[0] = next(iter(last_values.values())).sample_no
        
        prev_time = existing_values.get(1, 0.0)
        prev_amps = existing_values.get(3, 0.0)
        capacity_total = existing_values.get(5, 0.0)
        start_rec_no = existing_values.get(0, 0)
        for row_no, file_data_row in enumerate(file_cols_to_data_generator, 1):
            missing_colums = rec_col_set - set(file_data_row.keys())
            #            if (
            #                "dataset_id" in missing_colums
            #                and "dataset_id" in self.metadata
            #            ):
            #                file_data_row["dataset_id"] = self.metadata["dataset_id"]
            if 0 in missing_colums:  # sample_no
                file_data_row[0] = row_no
            if 5 in missing_colums:  # "capacity" / Charge Capacity
                current_amps = float(file_data_row[3])
                current_time = float(file_data_row[1])
                capacity_total += ((prev_amps + current_amps) / 2.0) * (
                    current_time - prev_time
                )
                file_data_row[5] = capacity_total
                prev_amps = current_amps
                prev_time = current_time
            #            if "power" in missing_colums:
            #                file_data_row["power"] = float(file_data_row["volts"]) * float(
            #                    file_data_row["amps"]
            #                )
            # file_data_row[col_name] if col_name in file_data_row else None
            if flag:
                print("Debug info")
                print(repr(file_data_row))
                print(repr(required_column_ids))
                flag = False
            # Should we just yield file_data_row, it should be exactly the same now
            yield {
                col_id: file_data_row[col_id] for col_id in required_column_ids
            }
            # yield [file_data_row[col_id] for col_id in required_column_ids]

    def get_data_with_standard_colums(
        self, required_column_ids, standard_cols_to_file_cols=None,
        last_values=None
    ):
        """
            Given a map of standard columns to file columns; return a map
            containing the given standard columns as keys with lists of data
            as values.
        """
        print("get_data_with_standard_colums")
        if standard_cols_to_file_cols is None:
            standard_cols_to_file_cols = {}
        print("Required columns: " + str(required_column_ids))
        # first determine
        file_col_to_std_col = {}
        print("Full type is " + str(self.type))
        # Get the column mappings the file type knows about
        file_col_to_std_col = self.get_file_column_to_standard_column_mapping()
        print("file_col_to_std_col 1: " + str(file_col_to_std_col))
        # extend those mappings with any custom ones provided
        file_col_to_std_col.update(
            {
                value: key
                for key, value in standard_cols_to_file_cols.items()
                if value is not None
            }
        )
        print("file_col_to_std_col 2: " + str(file_col_to_std_col))

        desired_file_cols_to_std_cols = {
            key: value
            for key, value in file_col_to_std_col.items()
            if value in required_column_ids
        }
        # Possible optimisation here:
        ## If we have last_values and the file has record numbers in
        ## then skip ahead until we reach the record after the one we have
        file_cols_to_data_generator = self.get_desired_data_if_present(
            desired_file_cols_to_std_cols
        )
        # pass file_cols_to_data_generator to generate missing column

        return self.complete_columns(
            required_column_ids, file_cols_to_data_generator, last_values
        )
        # return file_cols_to_data_generator

    def get_desired_data_if_present(self, desired_file_cols_to_std_cols=None):
        """
            now a generator
            Given a map of file_columns to standard_columns,
            get the file columns that are present,
            returns generator for each row of map of column id to value
        """
        if desired_file_cols_to_std_cols is None:
            desired_file_cols_to_std_cols = {}
        print("get_desired_data_if_present")
        print(
            "desired_file_cols_to_std_cols: "
            + str(desired_file_cols_to_std_cols)
        )
        # first find which desired columns are available
        available_columns = self.get_names_of_columns_with_data()
        available_desired_columns = available_columns & set(
            desired_file_cols_to_std_cols.keys()
        )
        print("available_desired_columns: " + str(available_desired_columns))
        # now load the available data
        # we need to pass whether the column is numeric to these
        if "MACCOR" in self.type:
            if "EXCEL" in self.type:
                return maccor_functions.load_data_maccor_excel(
                    self.file_path,
                    available_desired_columns,
                    desired_file_cols_to_std_cols,
                )
            else:
                # Handle csv, tsv and raw
                return maccor_functions.load_data_maccor_text(
                    self.type,
                    self.file_path,
                    available_desired_columns,
                    desired_file_cols_to_std_cols,
                )
        elif "IVIUM" in self.type:
            if "TXT" in self.type:
                return ivium_functions.load_data_ivium_text(
                    self.file_path,
                    available_desired_columns,
                    desired_file_cols_to_std_cols,
                )

        raise battery_exceptions.UnsupportedFileTypeError

    def get_data_row_generator(
        self,
        required_column_ids,
        dataset_id,
        record_no_column_id,
        standard_cols_to_file_cols=None,
        last_values=None,
    ):
        # given list of columns, map file columns to desired columns
        # load available columns
        # generate missing columns
        # store data values in map of standard columns to lists of data values
        # generate list of iterators of data columns in order of input list
        # yield a single line of tab separated quoted values
        if standard_cols_to_file_cols is None:
            standard_cols_to_file_cols = {}

        def tsv_format(value):
            # The psycopg2 cursor.copy_from method needs null values to be
            # represented as a literal '\N'
            return str(value) if value is not None else "\\N"

        try:
            for row in self.get_data_with_standard_colums(
                required_column_ids, standard_cols_to_file_cols, last_values
            ):
                rec_no = row[record_no_column_id]
                del row[record_no_column_id]
                for column_id, value in row.items():
                    timeseries_data_row = [
                        dataset_id,
                        rec_no,
                        column_id,
                        value,
                    ]
                    yield "\t".join(map(tsv_format, timeseries_data_row))
        except:
            traceback.print_exc()
            raise

    def get_data_labels(self):
        if "MACCOR" in self.type:
            return maccor_functions.generate_maccor_data_labels(
                self.type,
                self.file_path,
                [
                    column
                    for column, info in self.column_info.items()
                    if info["has_data"]
                ],
            )
        elif "IVIUM" in self.type:
            return ivium_functions.generate_ivium_data_labels(
                self.type,
                self.file_path,
                [
                    column
                    for column, info in self.column_info.items()
                    if info["has_data"]
                ],
            )
        raise battery_exceptions.UnsupportedFileTypeError

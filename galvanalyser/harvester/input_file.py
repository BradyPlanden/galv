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
from itertools import accumulate


# see https://gist.github.com/jsheedy/ed81cdf18190183b3b7d
# https://stackoverflow.com/a/30721460


def load_metadata(file_type, file_path):
    """
        Reads metadata contained in the file
    """
    if "MACCOR" in file_type:
        if "EXCEL" in file_type:
            return maccor_functions.load_metadata_maccor_excel(file_path)
        else:
            return maccor_functions.load_metadata_maccor_text(
                file_type, file_path
            )
    else:
        raise battery_exceptions.UnsupportedFileTypeError


def identify_columns(file_type, file_path):
    """
        Identifies which columns are present in the file and which have data
    """
    if "MACCOR" in file_type:
        if "EXCEL" in file_type:
            return maccor_functions.identify_columns_maccor_excel(file_path)
        else:
            return maccor_functions.identify_columns_maccor_text(
                file_type, file_path
            )
    else:
        raise battery_exceptions.UnsupportedFileTypeError


def identify_file(file_path):
    """
        Returns a string identifying the type of the input file
    """
    if file_path.endswith(".xls"):
        return "EXCEL-MACCOR"
    elif file_path.endswith(".csv"):
        return "CSV-MACCOR"
    elif file_path.endswith(".txt"):
        return "TSV-MACCOR"
    else:
        raise battery_exceptions.UnsupportedFileTypeError


def get_default_sample_time_setep(file_type):
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
        self.columns_with_data = identify_columns(self.type, file_path)
        self.metadata = load_metadata(self.type, file_path)
        # there should be some map of loaded data, not sure whether to use file cols or standard cols
        self.generated_columns = {}

    def get_test_start_date(self):
        # look check file type, ask specific implementation for metadata value
        pass
        return self.metadata["Date of Test:"]

    def generate_missing_columns(self, possibly_missing_colums, data):
        """
            Recursively generate missing columns.
            Some columns depend on the existence of others, this method
            generates the columns in order of fewest dependencies to most
            generating dependant columns first. Each recursion generates at
            most one column until all required columns are generated.
        """
        missing_colums = [
            col
            for col in possibly_missing_colums
            if col not in self.generated_columns.keys()
        ]
        changes_made = len(missing_colums) != len(possibly_missing_colums)
        num_rows = len(data[data.keys()[0]])

        if (
            "experiment_id" in missing_colums
            and "experiment_id" in self.meta_data
        ):
            self.generated_columns["experiment_id"] = (
                self.meta_data["experiment_id"] * num_rows
            )
            changes_made = True
        elif "sample_no" in missing_colums:
            self.generated_columns["sample_no"] = [
                i for i in range(1, num_rows + 1)
            ]
            changes_made = True
        elif "capacity" in missing_colums:
            self.generated_columns["sample_no"] = accumulate(data["amps"])
            changes_made = True
        elif "power" in missing_colums:
            power = [
                float(data["volts"][i]) * float(data["amps"][i])
                for i in range(num_rows)
            ]
            self.generated_columns["power"] = power
            changes_made = True

        if changes_made:
            return self.generate_missing_columns(missing_colums, data)
        elif len(missing_colums) > 0:
            print("Error missing these columns and unable to generate them:")
            print(missing_colums)
            raise battery_exceptions.DataGenerationError

    def get_generatable_columns(self):
        """
            Returns a list of columns that can be generated
        """
        return ["Cyc#", "State", "DPt Time", "Step", "StepTime", "Power"]

    def get_data_with_standard_colums(
        self, required_columns, standard_cols_to_file_cols={}
    ):
        """
            Given a map of standard columns to file columns; return a map
            containing the given standard columns as keys with lists of data
            as values.
        """
        output_columns = set(required_columns) | set(
            standard_cols_to_file_cols.keys()
        )
        # first determine
        file_col_to_std_col = {}
        if "MACCOR" in self.type:
            file_col_to_std_col = (
                maccor_functions.get_maccor_column_to_standard_column_mapping()
            )
        file_col_to_std_col.update(
            {
                value: key
                for key, value in standard_cols_to_file_cols.items()
                if value is not None
            }
        )
        #        file_col_to_std_col.update({standard_cols_to_file_cols[key]: key for
        #                                    key in standard_cols_to_file_cols.keys()
        #                                    if standard_cols_to_file_cols[key]
        #                                    is not None})
        file_cols_to_data = self.get_desired_data_if_present(
            file_col_to_std_col
        )

        # remap to standard colums : data
        standard_cols_to_data = {
            file_col_to_std_col[key]: value
            for key, value in file_cols_to_data.items()
        }
        # find the missing columns
        missing_std_cols = {
            col
            for col in output_columns
            if col not in standard_cols_to_data.keys()
        }
        # generate the missing columns
        self.generate_missing_columns(missing_std_cols, standard_cols_to_data)
        for missing_col in missing_std_cols:
            standard_cols_to_data[missing_col] = self.generated_columns[
                missing_col
            ]
        return standard_cols_to_data

    def get_desired_data_if_present(self, desired_file_cols_to_std_cols={}):
        """
            Given a map of file_columns to standard_columns,
            get the file columns that are present,
            return a map of standard_colums to lists of data
        """
        # first find which desired columns are available
        available_columns = {
            key
            for key, value in self.columns_with_data.items()
            if value["has_data"]
        }
        available_desired_columns = available_columns & set(
            desired_file_cols_to_std_cols.keys()
        )
        # now load the available data
        # we need to pass whether the column is numeric to these
        if "MACCOR" in self.type:
            if "EXCEL" in self.type:
                return maccor_functions.load_data_maccor_excel(
                    self.file_path, available_desired_columns
                )
            else:
                return maccor_functions.load_data_maccor_text(
                    self.type, self.file_path, available_desired_columns
                )
        else:
            raise battery_exceptions.UnsupportedFileTypeError

    def get_data_row_generator(self, required_column_names):
        # given list of columns, map file columns to desired columns
        # load available columns
        # generate missing columns
        # store data values in map of standard columns to lists of data values
        # generate list of iterators of data columns in order of input list
        # yield a single line of tab separated quoted values
        std_cols_to_data_map = self.get_data_with_standard_colums(
            required_column_names
        )
        iterators = [
            iter(std_cols_to_data_map[column])
            for column in required_column_names
        ]
        while True:
            yield "\t".join(
                [('"' + str(next(iterator)) + '"') for iterator in iterators]
            )

# -*- coding: utf-8 -*-

import arcpy
import pandas as pd
import numpy as np
import os

def load_field_selection(input_layer, fields = False, messages = False):
    '''
    Loads an ArcGIS attribute table into a DataFrame

    input_layer: String
        Name of the ArcGIS layer to load
    fields: List, default None
        List of fields to load to a DataFrame. If None, all fields will be
        loaded.
    '''

    # if fields have been specified
    if fields:
        InputTable = arcpy.da.TableToNumPyArray(
            input_layer, field_names = fields
            )
    # if no fields specified select all fields except for geometry fields
    else:
        field_names = [x.name for x in arcpy.ListFields(input_layer) if x.name != "SHAPE"]

        field_names = [x for x in field_names if x]

        if messages:
            messages.addMessage(field_names)

        InputTable = arcpy.da.TableToNumPyArray(
            input_layer, field_names = field_names
        )

    InputTable = pd.DataFrame(InputTable)

    return InputTable
    
def risk_in_range(
        x, LookUpTable, empty_val, lookup_NumericMinCol, lookup_NumericMaxCol, 
        lookup_RiskScoreCol
        ):
        '''
        Returns a risk value based on the numeric range that contains x. 
        Intended to be used within a row-wise function.

        x: Float
            Value to be tested against numeric ranges
        LookUpTable: DataFrame
            DataFrame containing numeric ranges and associates scores
        lookup_NumericMinCol: String
            Name of the field in LookUpTable containing minimum values
        lookup_NumericMaxCol: String
            Name of the field in LookUpTable containing maximum values
        lookup_RiskScoreCol: String
            Name of the field in LookUpTable containing risk scores
        '''
        risk_val = float(
            LookUpTable.loc[
                (x >= LookUpTable[lookup_NumericMinCol]) & 
                (x < LookUpTable[lookup_NumericMaxCol]), 
                lookup_RiskScoreCol
                ].max()
            )
        
        # if the risk val does not equal itself (i.e. NaN value)
        if risk_val != risk_val:
            # return the filler value
            return empty_val
        else:
            return risk_val
            
def risk_for_cat(
        x, LookUpTable, empty_val, lookup_CatCol, lookup_RiskScoreCol
        ):
        '''
        Returns a risk value based on the category that corresponds to x. 
        Intended to be used within a row-wise function.

        x: String
            Value to be tested against categories
        LookUpTable: DataFrame
            DataFrame containing categories and associates scores
        lookup_CatCol: String
            Name of the field in LookUpTable containing categories
        lookup_RiskScoreCol: String
            Name of the field in LookUpTable containing risk scores
        '''
        risk_val = float(
            LookUpTable.loc[
                LookUpTable[lookup_CatCol] == x,
                lookup_RiskScoreCol
                ].max()
            )
        # if the risk val does not equal itself (i.e. NaN value)
        if risk_val != risk_val:
            # return the filler value
            return empty_val
        else:
            return risk_val

def get_id_field(input, messages):
    '''
    Returns the ID field of the input layer

    input: String
        Name of the ArcGIS layer to get the ID field for
    messages: arcpy message object
        Used to write messages to the ArcGIS console when running
    '''
    # 
    fields = [x.name for x in arcpy.ListFields(input)]
    if 'OBJECTID' in fields:
        return 'OBJECTID'
    elif 'FID' in fields:
        return 'FID'
    elif 'objectid' in fields:
        return 'objectid'
    else:
        messages.addMessage(
            'No OBJECTID, FID, or objectid field'
            )

def duplicate_field_check(df_current_name, df_add, check_fields):
    '''
    Renames fields of a dataframe that are identical to the field names of a GIS
    layer. Renamed fields will be in the format FieldName_n.

    df_current_name: String
        Name of the ArcGIS layer that new fields will be added to

    df_add: DataFrame
        DataFrame containing data that will be added to df_current_name

    check_fields: List
        Fields to check for duplicate names. This list should exclude the ID
        field
    '''
    df_add = df_add.copy()
    # get the field names from the df_current_name layer
    df_current_fields = [
        x.name for x in arcpy.ListFields(df_current_name)
        ]
    rename_dict = {}
    for key in check_fields:
        # if the 10 character long field name is in the current list of
        # fields         
        if key[0:10] in df_current_fields:
            # create a field name that doesnt exist in the current df
            i = 1
            run = True
            while run:
                new_name = f'{key[0:9]}{i}'
                if new_name not in df_current_fields:
                    rename_dict[key] = new_name
                    run = False
                else:
                    i += 1
    # rename the columns in the dataframe
    df_add.rename(columns = rename_dict, inplace = True)

    return df_add

def remove_LLUR_overlaps(
    input, id_col, overlap_name, no_overlap_name,
    overlap_threshold
    ):
    '''
    IN DEV

    input : 
        polygon inputs to identify overlaps between
    id_col :
        "SiteID"
    overlap_name : 
        name of the layer that will be created showing overlaps between
    no_overlap_name :
        name of the output layer that will be the input layer without any
        overlaps exceeding 'overlap_percent'
    overlap_percent :
        the percent threshold
    '''
    
    #if the input is stored in layer group, seperate the layer name from
    # the folder path of the layer group
    input_name = input.split("\\")[-1]

    # create a layer of the intersecting area of polygons
    # the layer will go to the default geodatabase
    arcpy.analysis.Intersect(
        in_features = [input, input], 
        out_feature_class = overlap_name,
        join_attributes = "ALL"
        )
    
    # path to the new layer in the default gdb
    overlap_ref = os.path.join(arcpy.env.workspace, overlap_name)
    # remove all intersections that are the same polygons intersecting
    # one another (every polygon will intersect with itself if the)
    with arcpy.da.UpdateCursor(
        in_table = overlap_ref,
        field_names = [f"FID_{input_name}", f"FID_{input_name}_1"]) as cursor:
        for row in cursor:
            if row[0] == row[1]:
                cursor.deleteRow()
    # rename to fields to idenity the IDs of the parent and child polygons
    # parent is ...
    # child is ...
    field_renaming = {
        f"{id_col}": f"parent{id_col}",
        f"{id_col}_1": f"child{id_col}",
        f"FID_{input_name}": "parentPoly",
        f"FID_{input_name}_1": "childPoly",
        "AREA_M2": "parentArea",
        "AREA_M2_1": "childArea"
    }
    for f in field_renaming:
        
        arcpy.management.AlterField(
            in_table = overlap_ref,
            field = f,
            new_field_name = field_renaming[f],
            new_field_alias = field_renaming[f]
        )
    # remove unneeded fields
    discard = []
    keep = [field_renaming[f] for f in field_renaming]
    for field in [
        f.name for f in arcpy.ListFields(overlap_ref) if f.name not in [
            "OBJECTID", "Shape", "Shape_Area", "Shape_Length"
        ]]:
        if field not in keep:
            discard.append(field)
    arcpy.DeleteField_management(overlap_ref, discard)

    # add a universal ID for overlapping polygons
    codeblock = """def get_universal_id(id1, id2):
                        # pad each id with leading zeros to make a 6 
                        # digit string
                        id1_pad = str(id1).zfill(6)
                        id2_pad = str(id2).zfill(6)

                        id_l = [id1_pad, id2_pad]
                        id_l.sort()

                        id_ = ''.join(id_l)

                        return id_
                        """
    arcpy.management.CalculateField(
        in_table = overlap_ref,
        field = "UniversalID",
        expression = "get_universal_id(id1 = !parentPoly!, id2 = !childPoly!)",
        expression_type = "PYTHON3",
        code_block = codeblock,
        field_type = "FLOAT"
    )
    # calculate the percent overlap that the parent has over the child
    # if the overlap is 100%, the area of the parent polygon 100% overlaps the area of the child polygon
    # if the overlap is less than 100%, the parent polygon only partially covers the area of the child polygon
    arcpy.management.CalculateField(
        in_table = overlap_ref,
        field = "AreaPercent",
        expression = f"100*!Shape_Area!/!childArea!",
        expression_type = "PYTHON3",
        field_type = "FLOAT"
    )
    # identify overlapping polygons that have occured from drawing errors where 
    # the parent overlaps with the child < X% and
    # the child overlaps with the parent < X%
    # having this rule satisfied both ways means that small polygons intentionally
    # drawn within larger polygons will not be classed as mistakes

    # create a list of unversal IDs that DO NOT fit the drawer error
    # rules
    OIDs_not_errors = {}
    with arcpy.da.SearchCursor(
        in_table = overlap_ref,
        field_names = ["UniversalID", "AreaPercent"]) as cursor:
        for row in cursor:
            if row[0] not in OIDs_not_errors:
                if row[1] < overlap_threshold:
                    OIDs_not_errors[row[0]] = ["small overlap"]
                else:
                    OIDs_not_errors[row[0]] = ["large overlap"]
            else:
                if row[1] < overlap_threshold:
                    OIDs_not_errors[row[0]].append("small overlap")
                else:
                    OIDs_not_errors[row[0]].append("large overlap")
    
    # remove these polygons from the master layer
    with arcpy.da.UpdateCursor(
        in_table = overlap_ref,
        field_names = ["UniversalID"]) as cursor:
        for row in cursor:
            if "large overlap" in OIDs_not_errors[row[0]]:
                cursor.deleteRow()

    # remove the unintentional overlaps from the input layer
    arcpy.analysis.Erase(
        in_features = input,
        erase_features = overlap_ref,
        out_feature_class = no_overlap_name,
    )

class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "Risk Assessment Toolbox"
        self.alias = "risk_assessment"

        # List of tool classes associated with this toolbox
        self.tools = [
            risk_from_numeric_range,
            risk_from_category_value,
            custom_join,
            combine_LLUR_layers,
            combine_LLUR_layers_InDev,
            rank_column,
            count_numeric_range
            ]

class custom_join(object):

    '''
    Left join two GIS layers
    '''

    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Custom Join"
        self.description = "Custom Join"
        self.canRunInBackground = False
        self.custompath = r"\\fileservices02\Projects\SCI\ContaminatedLand\HAIL_RISK_MODELS\Contaminated Sites Risk Model - Region wide\Contaminated Sites Risk Model\Model_Output\Model_out.gdb\temp_right_table"


    def getParameterInfo(self):
        params = []

        left_input = arcpy.Parameter(
            displayName="Left Input",
            name="left_input",
            datatype="GPTableView",
            parameterType="Required",
            direction="Input"
        )
        right_input = arcpy.Parameter(
            displayName="Right Input",
            name="right_input",
            datatype="GPTableView",
            parameterType="Required",
            direction="Input"
        )
        left_join_fields = arcpy.Parameter(
            displayName="Left Join Fields",
            name="left_join_fields",
            datatype="Field",
            parameterType="Required",
            direction="Input",
            multiValue=True
        )
        right_join_fields = arcpy.Parameter(
            displayName="Right Join Fields",
            name="right_join_fields",
            datatype="Field",
            parameterType="Required",
            direction="Input",
            multiValue=True
        )
        right_fields_keep = arcpy.Parameter(
            displayName="Right Fields To Keep",
            name="right_fields_keep",
            datatype="GPString",
            parameterType="Optional",
            direction="Input",
            multiValue=True
        )
        #rename_right = arcpy.Parameter(
        #    displayName="Rename Right Fields",
        #    name="rename_right_fields",
        #    datatype="GPValueTable",
        #    parameterType="Optional",
        #    direction="Input"
        #)
        ##rename_right.columns = [
        #    ["GPString", "Rename From"],
        #    ["GPString", "Rename To"]
        #]

        output_field_count = arcpy.Parameter(
            displayName="Row Count",
            name="row_count",
            datatype="GPLong",
            parameterType="Derived",
            direction="Output"
        )

        left_join_fields.parameterDependencies = [left_input.name]
        right_join_fields.parameterDependencies = [right_input.name]

        params.extend([left_input, right_input, left_join_fields, right_join_fields,
                    right_fields_keep, output_field_count])
        
        #params.extend([left_input, right_input, left_join_fields, right_join_fields,
        #    right_fields_keep, rename_right, output_field_count])
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        if parameters[1].value and not parameters[1].hasBeenValidated:
            right_input = parameters[1].valueAsText
            fields = [f.name for f in arcpy.ListFields(right_input)]

            # Set ValueList filter for right_fields_keep
            parameters[4].filter.type = "ValueList"
            parameters[4].filter.list = fields

            # Ensure proper handling for rename_right, if needed
            #if parameters[5].value is None:
            #    parameters[5].value = [[field, field] for field in fields]
            return
       
    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        left_input = parameters[0].valueAsText
        messages.addMessage(f"left_input: {left_input}")
        right_input = parameters[1].valueAsText
        messages.addMessage(f"right_input: {right_input}")

        # Standardize join fields for both left and right inputs
        left_join_fields = parameters[2].valueAsText.split(';') if parameters[2].valueAsText else []
        messages.addMessage(f"left_join_fields: {left_join_fields}")

        right_join_fields = (
            parameters[3].valueAsText.split(';') if parameters[3].valueAsText else []
        )
        messages.addMessage(f"right_join_fields: {right_join_fields}")

        right_fields_keep = parameters[4].valueAsText.split(';') if parameters[4].valueAsText else []
        messages.addMessage(f"right_fields_keep: {right_fields_keep}")

        try:
            temp_table = "in_memory\\temp_table"

            if arcpy.Exists(temp_table):
                arcpy.management.Delete(temp_table)

            # Export right_input to an in-memory table
            arcpy.conversion.TableToTable(
                in_rows=right_input,
                out_path="in_memory",
                out_name="temp_table"
            )

            # Standardize join field data types in the right table
            fields = arcpy.ListFields(temp_table)
            field_names = [field.name for field in fields]

            for field in fields:
                messages.addMessage(f"Name: {field.name}, Type: {field.type}")

            if right_join_fields and right_join_fields[0] not in field_names:
                messages.addMessage(f"{right_join_fields[0]} not in {field_names}")
                join_field = "FID" if "FID" in field_names else "OID"
                right_join_fields[0] = join_field

            messages.addMessage(f"Using right join field: {right_join_fields[0]}")

            # Force the right join field to match the left join field type
            left_field_type = next((field.type for field in arcpy.ListFields(left_input) if field.name == left_join_fields[0]), None)
            right_field_type = next((field.type for field in arcpy.ListFields(temp_table) if field.name == right_join_fields[0]), None)

            if left_field_type and right_field_type and left_field_type != right_field_type:
                messages.addMessage(f"Converting right join field '{right_join_fields[0]}' from {right_field_type} to {left_field_type}")
                arcpy.management.AddField(
                    in_table=temp_table,
                    field_name="temp_right_join",
                    field_type=left_field_type
                )

                arcpy.management.CalculateField(
                    in_table=temp_table,
                    field="temp_right_join",
                    expression=f"!{right_join_fields[0]}!",
                    expression_type="PYTHON3"
                )

                right_join_fields[0] = "temp_right_join"

            # Preview the first 10 values in the right join field
            if right_join_fields:
                values = []

                with arcpy.da.SearchCursor(temp_table, right_join_fields[0]) as cursor:
                    for i, row in enumerate(cursor):
                        if i >= 10:
                            break
                        values.append(row[0])

                messages.addMessage(f"First 10 values of {right_join_fields[0]}: {values}")
            else:
                messages.addMessage("right_join_fields[0] is not defined or empty.")

            if left_join_fields:
                values = []

                with arcpy.da.SearchCursor(left_input, left_join_fields[0]) as cursor:
                    for i, row in enumerate(cursor):
                        if i >= 10:
                            break
                        values.append(row[0])

                messages.addMessage(f"First 10 values of {left_join_fields[0]}: {values}")
            else:
                messages.addMessage("right_join_fields[0] is not defined or empty.")

            # Standardize join field data types in the left table
            fields = arcpy.ListFields(left_input)
            field_names = [field.name for field in fields]

            for field in fields:
                messages.addMessage(f"Name: {field.name}, Type: {field.type}")

            if left_join_fields and left_join_fields[0] not in field_names:
                raise ValueError(f"Left join field {left_join_fields[0]} does not exist in {left_input}.")

            # Perform the join
            arcpy.management.JoinField(
                in_data=left_input,
                in_field=left_join_fields[0],
                join_table=temp_table,
                join_field=right_join_fields[0],
                fields=right_fields_keep
            )

        except arcpy.ExecuteError as err:
            messages.addErrorMessage(str(err))
            raise

        row_count = arcpy.management.GetCount(left_input)[0]
        parameters[5].value = row_count

        fields = arcpy.ListFields(left_input)
        for field in fields:
            messages.addMessage(f"Name: {field.name}, Type: {field.type}")

        messages.addMessage("Successfully merged table")
        return





class combine_LLUR_layers(object):

    '''
    Combine the LLUR site and activity layers based on overlap 
    '''

    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Combine LLUR Layers"
        self.description = "Combine LLUR Layers"
        self.canRunInBackground = False

    def getParameterInfo(self):
        
        params = []
        # Parameter 1: Input feature layer
        ActivityLayer = arcpy.Parameter(
            displayName = "Activity Layer",
            name = "ActivityLayer",
            datatype = "GPTableView",
            parameterType = "Required",
            direction = "Input"
        )
        SiteLayer = arcpy.Parameter(
            displayName = "Site Layer",
            name = "SiteLayer",
            datatype = "GPTableView",
            parameterType = "Required",
            direction = "Input"
        )
        output = arcpy.Parameter(
            displayName="Output Intersected Polygon",
            name="output_intersect",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Output"
        )
        OverlapPerc = arcpy.Parameter(
            displayName="Overlap Percentage Threshold",
            name="overlap_percentage_threshold",
            datatype="GPLong",
            parameterType="Required",
            direction="Input"
        )

        params.append(ActivityLayer)
        params.append(SiteLayer)
        params.append(output)
        params.append(OverlapPerc)

        return params
 
    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""

        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):

        activities = parameters[0].valueAsText
        sites = parameters[1].valueAsText
        output = parameters[2].valueAsText
        overlap_threshold = parameters[3].value

        # create a layer of polygons at covering the intersecting area of
        # "Sites" and "Activities"
        arcpy.analysis.Intersect(
            in_features = [activities, sites], 
            out_feature_class = output
            )
        
        # Calculate areas of intersected polygons
        arcpy.management.CalculateGeometryAttributes(output, [["SiteAct_A", "AREA"]])        
        # Add a field to store the overlap percentage
        arcpy.management.AddField(output, "Area_Per", "DOUBLE")
        # Add a field to stored whether an activity is fully contained within a
        # site
        arcpy.management.AddField(output, "Full_Con", "SHORT")
        # Add a combined UID field
        arcpy.management.AddField(output, "HAIL_UID", "TEXT")

        # Calculate areas and geometries of the "Sites" polygons
        site_area_dict = {}
        site_geom_dict = {}
        with arcpy.da.SearchCursor(
            in_table = sites, 
            field_names = ["OBJECTID", "SHAPE@AREA", "SHAPE@"]
            ) as cursor:
            for row in cursor:
                site_area_dict[row[0]] = row[1]
                site_geom_dict[row[0]] = row[2]
        # Calculate the geometries of the "Activities" polygons
        activity_geom_dict = {}
        with arcpy.da.SearchCursor(
            in_table = activities,
            field_names = ['OBJECTID', "SHAPE@"]
            ) as cursor:
            for row in cursor:
                activity_geom_dict[row[0]] = row[1]

        # Calculate the % area coverage that the "Site-Acitivity" polygons have
        # with the surrounding "Site" polgons and check if each "Site-Activity"
        # polygon is fully contained with a "Site" polygon
        with arcpy.da.UpdateCursor(
            in_table = output, 
            field_names = [    
                "FID_L1Sites",      #0
                "FID_L5Activities", #1
                "SHAPE@",           #2
                "SHAPE@AREA",       #3
                "Area_Per",         #4
                "Full_Con",         #5
                "HAIL_UID",         #6
                "SiteID",           #7
                "HAILNo"            #8
                ]
            ) as cursor:
            for row in cursor:
                input2_area = site_area_dict[int(row[0])]
                overlap_percent = (row[3] / input2_area) * 100
                row[4] = overlap_percent

                is_fully_contained = site_geom_dict[int(row[0])].contains(activity_geom_dict[int(row[1])])
                if is_fully_contained:
                    row[5] = 1
                else:
                    row[5] = 0

                row[6] = f'{row[7]}_{row[8]}'

                cursor.updateRow(row)

        # Delete polygons where overlap percentage is 5% or less and the not
        # fully contained
        with arcpy.da.UpdateCursor(
            in_table = output,
            field_names = ["Area_Per", "Full_Con"]
            ) as cursor:
            for row in cursor:
                if row[0] <= overlap_threshold and row[1] == 0:
                    cursor.deleteRow()
        
        return

class combine_LLUR_layers_InDev(object):

    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Combine LLUR Layers In Dev"
        self.description = "Combine LLUR Layers In Dev"
        self.canRunInBackground = False

    def getParameterInfo(self):
        
        params = []
        # Parameter 1: Input feature layer
        ActivityLayer = arcpy.Parameter(
            displayName = "Activity Layer",
            name = "ActivityLayer",
            datatype = "GPTableView",
            parameterType = "Required",
            direction = "Input"
        )
        SiteLayer = arcpy.Parameter(
            displayName = "Site Layer",
            name = "SiteLayer",
            datatype = "GPTableView",
            parameterType = "Required",
            direction = "Input"
        )
        output = arcpy.Parameter(
            displayName="Output Intersected Polygon",
            name="output_intersect",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Output"
        )
        OverlapPerc = arcpy.Parameter(
            displayName="Overlap Percentage Threshold",
            name="overlap_percentage_threshold",
            datatype="GPLong",
            parameterType="Required",
            direction="Input"
        )

        params.append(ActivityLayer)
        params.append(SiteLayer)
        params.append(output)
        params.append(OverlapPerc)

        return params
 
    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""

        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
            
        activities = parameters[0].valueAsText
        sites = parameters[1].valueAsText
        output = parameters[2].valueAsText
        overlap_threshold = parameters[3].value

        # remove overlaps across the sites layer
        remove_LLUR_overlaps(
            input = sites,
            id_col = "SiteID",
            overlap_name = "LLUR_sites_overlap",
            no_overlap_name = "LLUR_sites_NO_overlap",
            overlap_threshold = overlap_threshold
            )
        # remove overlaps across the activities layer
        remove_LLUR_overlaps(
            input = activities,
            id_col = "HAILNo",
            overlap_name = "LLUR_act_overlap",
            no_overlap_name = "LLUR_act_NO_overlap",
            overlap_threshold = overlap_threshold
        )
        # create a layer of polygons at covering the intersecting area of
        # "Sites" and "Activities"
        arcpy.analysis.Intersect(
            in_features = [
                os.path.join(arcpy.env.workspace, "LLUR_act_NO_overlap"), 
                os.path.join(arcpy.env.workspace, "LLUR_sites_NO_overlap")
                ], 
            out_feature_class = output
            )
        # Calculate areas of intersected polygons
        arcpy.management.CalculateGeometryAttributes(output, [["SiteAct_A", "AREA"]])
        
        # Add a field to store the overlap percentage
        arcpy.management.AddField(output, "Area_Per", "DOUBLE")
        # Add a field to stored whether an activity is fully contained within a
        # site
        arcpy.management.AddField(output, "Full_Con", "SHORT")
        # Add a combined UID field
        arcpy.management.AddField(output, "HAIL_UID", "TEXT")

        # Calculate areas and geometries of the "Sites" polygons
        site_area_dict = {}
        site_geom_dict = {}
        with arcpy.da.SearchCursor(
            in_table = os.path.join(arcpy.env.workspace, "LLUR_sites_NO_overlap"), 
            field_names = ["OBJECTID", "SHAPE@AREA", "SHAPE@"]
            ) as cursor:
            for row in cursor:
                site_area_dict[row[0]] = row[1]
                site_geom_dict[row[0]] = row[2]

        # Calculate the geometries of the "Activities" polygons
        activity_geom_dict = {}
        with arcpy.da.SearchCursor(
            in_table = os.path.join(arcpy.env.workspace, "LLUR_act_NO_overlap"),
            field_names = ['OBJECTID', "SHAPE@"]
            ) as cursor:
            for row in cursor:
                activity_geom_dict[row[0]] = row[1]

        # Calculate the % area coverage that the "Site-Acitivity" polygons have
        # with the surrounding "Site" polgons and check if each "Site-Activity"
        # polygon is fully contained with a "Site" polygon

        with arcpy.da.UpdateCursor(
            in_table = output, 
            field_names = [    
                #"FID_L1Site",       #0
                "FID_LLUR_sites_NO_overlap",
                #"FID_L5Acti",       #1
                "FID_LLUR_act_NO_overlap",
                "SHAPE@",           #2
                "SHAPE@AREA",       #3
                "Area_Per",         #4
                "Full_Con",         #5
                "HAIL_UID",         #6
                "SiteID",           #7
                "HAILNo"            #8
                ]
            ) as cursor:
            for row in cursor:
                input2_area = site_area_dict[int(row[0])]
                overlap_percent = (row[3] / input2_area) * 100
                row[4] = overlap_percent

                is_fully_contained = site_geom_dict[int(row[0])].contains(activity_geom_dict[int(row[1])])
                if is_fully_contained:
                    row[5] = 1
                else:
                    row[5] = 0

                row[6] = f'{row[7]}_{row[8]}'

                cursor.updateRow(row)

        # Delete polygons where overlap percentage is 5% or less and the not
        # fully contained
        with arcpy.da.UpdateCursor(
            in_table = output,
            field_names = ["Area_Per", "Full_Con"]
            ) as cursor:
            for row in cursor:
                if row[0] <= overlap_threshold and row[1] == 0:
                    cursor.deleteRow()

        return
        
class risk_from_category_value(object):
    '''
    Adds a new field to a GIS layer that contains values based on a lookup csv
    file with the columns 'PARAMETER' and 'SCORE'. The PARAMTER column
    corresponds to a field that already exists in the GIS layer and the SCORE
    column contains values that will be added in the new column
    '''

    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Risk From Category Values"
        self.description = "Adds a risk column to the input layer based on the lookup table."
        self.canRunInBackground = False

    def getParameterInfo(self):

        params = []
        # Parameter 1: Input feature layer
        input_layer = arcpy.Parameter(
            displayName = "Input Layer",
            name = "input_layer",
            datatype = "GPTableView",
            parameterType = "Required",
            direction = "Input"
        )
        # Parameter 2: Scoring Field
        scoring_field = arcpy.Parameter(
            displayName = "Scoring Field",
            name = "scoring_field",
            datatype = "Field",
            parameterType = 'Required',
            direction = "Input"
        )
        # Parameter 3: Lookup table
        lookup_table = arcpy.Parameter(
            displayName = "Lookup Table",
            name = "lookup_table",
            datatype = "GPTableView",
            parameterType = "Required",
            direction = "Input"
        )
        # Parameter 4: Empty value
        empty_value = arcpy.Parameter(
            displayName = "Empty Value Substitute",
            name = "empty",
            datatype = "Double",
            parameterType = "Required",
            direction = "Input"
        )
        # Parameter 5: Output Field Name
        output_field_name = arcpy.Parameter(
            displayName = "Output Field Name",
            name = "output_field_name",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input"
        )
        # Parameter 6: Row count output
        output_field_count = arcpy.Parameter(
            displayName="Row Count",
            name="row_count",
            datatype="GPLong",
            parameterType="Derived",
            direction="Output"
        )

        scoring_field.parameterDependencies = [input_layer.name]

        params.append(input_layer)
        params.append(scoring_field)
        params.append(lookup_table)
        params.append(empty_value)
        params.append(output_field_name)
        params.append(output_field_count)

        return params
    
    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""

        lookup_CatCol = 'PARAMETER'
        lookup_RiskScoreCol = 'SCORE'

        input_layer = parameters[0].valueAsText
        scoring_field = parameters[1].valueAsText
        LookUpTable = parameters[2].valueAsText
        empty_val = parameters[3].valueAsText
        output_field_name = parameters[4].valueAsText

        empty_val = float(empty_val)

        # get the ID field of the input layer
        id_field = get_id_field(input = input_layer, messages = messages)

        # Load the input layer table
        InputTable = load_field_selection(
            input_layer = input_layer,
            fields = [id_field, scoring_field]
        )

        # Load the lookup table
        LookUpTable = arcpy.da.TableToNumPyArray(LookUpTable, "*")
        LookUpTable = pd.DataFrame(LookUpTable)

        # Add the risk score column based on 
        InputTable[output_field_name] = InputTable[scoring_field].apply(
            lambda x: risk_for_cat(
                x = x, LookUpTable = LookUpTable, empty_val = empty_val,
                lookup_CatCol = lookup_CatCol,
                lookup_RiskScoreCol = lookup_RiskScoreCol
                )
            )
        # Limit the fields to only ID and score
        InputTable = InputTable[[id_field, output_field_name]]
        # Convert merged DataFrame back to numpy array
        InputTable = InputTable.to_records(index = False)
        # Update input layer with new Risk column
        arcpy.da.ExtendTable(
            input_layer, id_field, InputTable, id_field, append_only=False
            )
        
        row_count = arcpy.management.GetCount(input_layer)[0]
        parameters[5].value = row_count

        return

class rank_column(object):
    '''
    Create a ranking column based on numbers in a chosen column. The ranking
    style is 'Standard competition ranking'.
    '''
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Rank column"
        self.description = "Rank column"
        self.canRunInBackground = False

    def getParameterInfo(self):

        params = []
        input_layer = arcpy.Parameter(
            displayName = "Input Layer",
            name = "input_layer",
            datatype = "GPTableView",
            parameterType = "Required",
            direction = "Input"
        )
        ranking_field = arcpy.Parameter(
            displayName = "Ranking Field",
            name = "ranking_field",
            datatype = "Field",
            parameterType = 'Required',
            direction = "Input"
        )
        output_field_name = arcpy.Parameter(
            displayName = "Output Field Name",
            name = "output_field_name",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input"
        )
        output_field_count = arcpy.Parameter(
            displayName="Row Count",
            name="row_count",
            datatype="GPLong",
            parameterType="Derived",
            direction="Output"
        )

        ranking_field.parameterDependencies = [input_layer.name]

        params.append(input_layer)
        params.append(ranking_field)
        params.append(output_field_name)
        params.append(output_field_count)

        return params
    
    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""

        input_layer = parameters[0].valueAsText
        ranking_field = parameters[1].valueAsText
        output_field_name = parameters[2].valueAsText

        allValues = []
        with arcpy.da.SearchCursor(
            in_table = input_layer,
            field_names = [ranking_field]) as searchCursor:
            for row in searchCursor:
                allValues.append(row[0])

        allValues_sorted = sorted(allValues, reverse=True)  

        lookup = {}
        count = 1
        for i in range(len(allValues_sorted)):
            if lookup == {} or allValues_sorted[i-1] != allValues_sorted[i]:
                lookup[allValues_sorted[i]] = count
            else:
                lookup[allValues_sorted[i]] = lookup[allValues_sorted[i-1]]
            count += 1

        arcpy.management.AddField(in_table = input_layer, field_name = output_field_name, field_type = "LONG")

        with arcpy.da.UpdateCursor(input_layer, [ranking_field, output_field_name]) as updateCursor:
            for row in updateCursor:
                row[1] = lookup[row[0]]
                updateCursor.updateRow(row)

        row_count = arcpy.management.GetCount(input_layer)[0]
        parameters[3].value = row_count

        return


        #-----------------------------------------------------------------------
        # allValues = set()
        # with arcpy.da.SearchCursor(
        #     in_table = input_layer,
        #     field_names = [ranking_field]) as searchCursor:
        #     for row in searchCursor:
        #         allValues.add(row[0])
 
        # # Create a value/rank lookup
        # lookup = { value : rank + 1 for (rank, value) in  enumerate(sorted(allValues, reverse=True))}

        # arcpy.management.AddField(in_table = input_layer, field_name = output_field_name, field_type = "DOUBLE")

        # # Set the ranks on the rows
        # with arcpy.da.UpdateCursor(input_layer, [ranking_field, output_field_name]) as updateCursor:
        #     for row in updateCursor:
        #         row[1] = lookup[row[0]]
        #         updateCursor.updateRow(row)

        # row_count = arcpy.management.GetCount(input_layer)[0]
        # parameters[3].value = row_count

        # return

class count_numeric_range(object):
    '''
    Counts the number of fields that are within specified numeric ranges. E.g.
    create columns Count0_20, Count20_40 that contains counts of columns that
    contain values between 0-20 and 20-40 for each row
    '''

    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Count numeric range"
        self.description = "Count numeric range"
        self.canRunInBackground = False
    
    def getParameterInfo(self):
        
        params = []

        input_layer = arcpy.Parameter(
            displayName = "Input Layer",
            name = "input_layer",
            datatype = "GPTableView",
            parameterType = "Required",
            direction = "Input"
        )
        input_fields = arcpy.Parameter(
            displayName = "Input Fields",
            name = "input_fields",
            datatype = "Field",
            parameterType = 'Required',
            direction = "Input",
            multiValue=True
        )
        numeric_ranges = arcpy.Parameter(
            displayName="Numeric Ranges",
            name="numeric_ranges",
            datatype="GPValueTable",
            parameterType="Optional",
            direction="Input"
        )
        numeric_ranges.columns = [
            ["GPLong", "Lower Bound"],
            ["GPLong", "Upper Bound"],
            ["GPString", "Output Field Name"],
            ]
        
        input_fields.parameterDependencies = [input_layer.name]
        
        params.append(input_layer)
        params.append(input_fields)
        params.append(numeric_ranges)
        
        return params
        
    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True
    
    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""

        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return
    
    def execute(self, parameters, messages):

        # input layer
        input_layer = parameters[0].valueAsText
        # input columns
        _input_columns = parameters[1].valueAsText
        input_columns = _input_columns.split(';')
        # numeric ranges
        numeric_ranges = {}
        _numeric_ranges = parameters[2].value
        for x in _numeric_ranges:
            numeric_ranges[x[2]] = {
                'lower_bound': x[0],
                'upper_bound': x[1]
            }

        for f in list(numeric_ranges.keys()):
            arcpy.management.AddField(
                in_table = input_layer,
                field_name = str(f),
                field_type = "DOUBLE"
                )

        # for each output column
        arcpy.AddMessage("Evaluating")
        for count_col in numeric_ranges:
            arcpy.AddMessage(count_col)
            with arcpy.da.UpdateCursor(input_layer, [count_col] + input_columns) as updateCursor:
                for row in updateCursor:
                    
                    lower_bound = numeric_ranges[count_col]['lower_bound']
                    upper_bound = numeric_ranges[count_col]['upper_bound']

                    count = 0
                    for input_col_ind in range(len(input_columns)):
                        if row[input_col_ind + 1] >= lower_bound and  row[input_col_ind + 1] < upper_bound:
                            count += 1

                    row[0] = count

                    updateCursor.updateRow(row)
        
        return

class risk_from_numeric_range(object):
    
    '''
    Adds a new field to a GIS layer that contains values based on a lookup csv
    file with the columns 'MIN', 'MAX' and 'SCORE'. The MIN and MAX columns
    correspond to fields that already exists in the GIS layer and scores will
    be added for values that are greater-and-equal-to MIN and less-than MAX.
    '''

    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Risk From Numeric Range"
        self.description = "Adds a risk column to the input layer based on the lookup table."
        self.canRunInBackground = False

    def getParameterInfo(self):

        params = []
        # Parameter 1: Input feature layer
        input_layer = arcpy.Parameter(
            displayName = "Input Layer",
            name = "input_layer",
            datatype = "GPFeatureLayer",
            parameterType = "Required",
            direction = "Input"
        )
        # Parameter 2: Scoring Field
        scoring_field = arcpy.Parameter(
            displayName = "Scoring Field",
            name = "scoring_field",
            datatype = "Field",
            parameterType = 'Required',
            direction = "Input"
        )
        # Parameter 3: Lookup table
        lookup_table = arcpy.Parameter(
            displayName = "Lookup Table",
            name = "lookup_table",
            datatype = "GPTableView",
            parameterType = "Required",
            direction = "Input"
        )
        # Parameter 4: Empty value
        empty_value = arcpy.Parameter(
            displayName = "Empty Value Substitute",
            name = "empty",
            datatype = "Double",
            parameterType = "Required",
            direction = "Input"
        )
        # Parameter 5: Output Field Name
        output_field_name = arcpy.Parameter(
            displayName = "Output Field Name",
            name = "output_field_name",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input"
        )
        # Parameter 6: 
        output_field_count = arcpy.Parameter(
            displayName="Row Count",
            name="row_count",
            datatype="GPLong",
            parameterType="Derived",
            direction="Output"
        )
        scoring_field.parameterDependencies = [input_layer.name]

        params.append(input_layer)
        params.append(scoring_field)
        params.append(lookup_table)
        params.append(empty_value)
        params.append(output_field_name)
        params.append(output_field_count)

        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""

        # If input_layer has been updated, refresh scoring_field
        if parameters[0].altered and parameters[0].value:  # Check if the input_layer has changed
            parameters[1].parameterDependencies = [parameters[0].name]
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""

        lookup_NumericMinCol = 'MIN'
        lookup_NumericMaxCol = 'MAX'
        lookup_RiskScoreCol = 'SCORE'

        input_layer = parameters[0].valueAsText
        scoring_field = parameters[1].valueAsText
        LookUpTable = parameters[2].valueAsText
        empty_val = parameters[3].valueAsText
        output_field_name = parameters[4].valueAsText

        empty_val = float(empty_val)

        # get the ID field of the input layer
        id_field = get_id_field(input = input_layer, messages = messages)

        # Load the input layer table
        InputTable = load_field_selection(
            input_layer = input_layer,
            fields = [id_field, scoring_field]
        )

        # Load the lookup table
        LookUpTable = arcpy.da.TableToNumPyArray(LookUpTable, "*")
        LookUpTable = pd.DataFrame(LookUpTable)

        # Add the risk score column based on 
        InputTable[output_field_name] = InputTable[scoring_field].apply(
            lambda x: risk_in_range(
                x = x, LookUpTable = LookUpTable, empty_val = empty_val,
                lookup_NumericMinCol = lookup_NumericMinCol,
                lookup_NumericMaxCol = lookup_NumericMaxCol,
                lookup_RiskScoreCol = lookup_RiskScoreCol
                )
            )        
        # Limit the fields to only ID and score
        InputTable = InputTable[[id_field, output_field_name]]
        # Convert merged DataFrame back to numpy array
        InputTable = InputTable.to_records(index = False)
        # Update input layer with new Risk column
        arcpy.da.ExtendTable(
            input_layer, id_field, InputTable, id_field, append_only=False
            )
        
        row_count = arcpy.management.GetCount(input_layer)[0]
        parameters[5].value = row_count

        return
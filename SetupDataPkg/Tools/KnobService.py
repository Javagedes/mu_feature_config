# @ KnobService.py
#
# Generates C header files for a firmware component to consume UEFI variables
# as configurable knobs
#
# Copyright (c) 2022, Microsoft Corporation. All rights reserved.
#
import os
import sys
import uuid
import re
import VariableList


# Converts a type name from standard C to UEFI
def get_type_string(type_name, uefi=False):
    uefi_types = {
        "int8_t": "INT8",
        "int16_t": "INT16",
        "int32_t": "INT32",
        "int64_t": "INT64",
        "uint8_t": "UINT8",
        "uint16_t": "UINT16",
        "uint32_t": "UINT32",
        "uint64_t": "UINT64",
        "bool": "BOOLEAN",
        "float": "float",
        "double": "double",
        "size_t": "UINTN",
        "int": "INTN",
        "const": "CONST",
        "void*": "VOID *",
        "char*": "CHAR8 *",
        "config_guid_t": "EFI_GUID",
        "void": "VOID"
    }
    if uefi:
        if type_name in uefi_types:
            return uefi_types[type_name]

    return type_name


# Converts a value from standard C to UEFI
def get_value_string(value, uefi=False):
    if value == "true" and uefi:
        return "TRUE"
    elif value == "false" and uefi:
        return "FALSE"
    else:
        return value


# UEFI uses 2 spaces, stdlibc uses 4 spaces
def get_spacing_string(uefi=False, num=1):
    spaces = ""
    for i in range(0, num):
        if uefi is True:
            spaces += "  "
        else:
            spaces += "    "

    return spaces


# UEFI style uses CRLF line endings
def get_line_ending(uefi=False):
    if uefi is True:
        return "\r\n"

    return "\n"


# UEFI style uses #ifdef instead of pragma once
def get_include_once_style(name, uefi=False, header=True):
    if uefi is True:
        # convert . to _
        while match := re.search(r'\.', name):
            name = name[:match.start()] + "_" + name[match.end():]
        if header is True:
            return "#ifndef " + name.upper() + get_line_ending(uefi) + "#define " + name.upper() + get_line_ending(uefi)
        else:
            return "#endif // " + name.upper() + get_line_ending(uefi)
    elif header is True:
        return "#pragma once" + get_line_ending(uefi)
    else:
        return get_line_ending(uefi)


# Convert std libc variable/structure/type naming conventions to UEFI naming conventions
def naming_convention_filter(value, type, uefi=False):
    if not uefi:
        return value

    if type is True:
        # types will be in format THIS_IS_THE_TYPE_NAME
        # std libc likes to append '_t' to type names, strip that for UEFI
        if value[-2:] == "_t":
            value = value[:-2]
        return value.upper()
    else:
        # fields and functions will be in format ThisIsTheName

        # if the first char is an underscore, strip it
        if value[0] == "_":
            value = value[1:]

        # capitalize first word (may be single word)
        value = value[0].upper() + value[1:]

        # remove any trailing underscore
        if value[-1] == "_":
            value = value[:-1]

        # remove the underscores and capitalize each word
        while match := re.search("_", value):
            value = value[:match.start()] + value[match.end()].upper() + value[match.end() + 1:]

    return value


# return proper assert style for efi/non-efi builds
def get_assert_style(uefi, assert_string, msg):
    if uefi is True:
        return "STATIC_ASSERT" + assert_string + ", " + msg + ");"

    return "C_ASSERT" + assert_string + ");"


def generate_public_header(schema, header_path, efi_type=False):

    format_options = VariableList.StringFormatOptions()
    format_options.c_format = True
    format_options.efi_format = efi_type

    with open(header_path, 'w', newline='') as out:
        out.write(get_include_once_style(header_path, uefi=efi_type, header=True))
        # UEFI uses Uefi.h instead of std libc headers
        if efi_type:
            out.write("#include <Uefi.h>" + get_line_ending(efi_type))
        else:
            out.write("#include <stdint.h>" + get_line_ending(efi_type))
            out.write("#include <stddef.h>" + get_line_ending(efi_type))
            out.write("#include <stdbool.h>" + get_line_ending(efi_type))
        out.write("// Generated Header" + get_line_ending(efi_type))
        out.write("//  Script: {}".format(sys.argv[0]) + get_line_ending(efi_type))
        out.write("//  Schema: {}".format(schema.path) + get_line_ending(efi_type))
        out.write("" + get_line_ending(efi_type))
        # UEFI code uses STATIC_ASSERT, already defined in the environment
        if not efi_type:
            out.write("#ifndef C_ASSERT" + get_line_ending(efi_type))
            out.write("// Statically verify an expression" + get_line_ending(efi_type))
            out.write("#define C_ASSERT(e) typedef char __C_ASSERT__[(e)?1:-1]" + get_line_ending(efi_type))
            out.write("#endif" + get_line_ending(efi_type))
            out.write("" + get_line_ending(efi_type))
        out.write("#pragma pack(push, 1)")
        out.write("" + get_line_ending(efi_type))
        out.write("// Schema-defined enums" + get_line_ending(efi_type))
        for enum in schema.enums:
            if enum.help != "":
                out.write("// {}".format(enum.help) + get_line_ending(efi_type))
            out.write("typedef enum {" + get_line_ending(efi_type))
            has_negative = False
            for value in enum.values:
                if value.help != "":
                    out.write(get_spacing_string(efi_type) + "{}_{} = {}, // {}".format(
                        enum.name,
                        value.name,
                        value.number,
                        value.help
                    ) + get_line_ending(efi_type))
                else:
                    out.write(get_spacing_string(efi_type) + "{}_{} = {},".format(
                        enum.name,
                        value.name,
                        value.number
                    ) + get_line_ending(efi_type))

                if value.number < 0:
                    has_negative = True
            if has_negative:
                out.write(get_spacing_string(efi_type) + "_{}_PADDING = 0x7fffffff // Force packing to int size".format(
                    enum.name
                ) + get_line_ending(efi_type))
            else:
                out.write(get_spacing_string(efi_type) + "_{}_PADDING = 0xffffffff // Force packing to int size".format(
                    enum.name
                ) + get_line_ending(efi_type))
            out.write("}} {};".format(enum.name) + get_line_ending(efi_type))
            out.write("" + get_line_ending(efi_type))
            assert_string = f"(sizeof({enum.name}) == sizeof({get_type_string('uint32_t', efi_type)})"
            out.write(get_assert_style(efi_type, assert_string, '"enum must be unsigned 32 bit int"'))
            out.write(get_line_ending(efi_type))
            out.write("" + get_line_ending(efi_type))
            pass

        out.write("// Schema-defined structures" + get_line_ending(efi_type))
        for struct_definition in schema.structs:
            if struct_definition.help != "":
                out.write("// {}".format(struct_definition.help) + get_line_ending(efi_type))
            out.write("typedef struct {" + get_line_ending(efi_type))
            for member in struct_definition.members:
                if member.help != "":
                    out.write(get_spacing_string(efi_type) + "// {}".format(member.help) + get_line_ending(efi_type))
                if member.count == 1:
                    out.write(get_spacing_string(efi_type) + "{} {};".format(
                        get_type_string(member.format.c_type, efi_type),
                        member.name) + get_line_ending(efi_type))
                else:
                    out.write(get_spacing_string(efi_type) + "{} {}[{}];".format(
                        get_type_string(member.format.c_type, efi_type),
                        member.name,
                        member.count) + get_line_ending(efi_type))

            out.write("}} {};".format(struct_definition.name) + get_line_ending(efi_type))
            out.write("" + get_line_ending(efi_type))
            out.write(get_assert_style(efi_type, "(sizeof({}) == {}".format(
                struct_definition.name,
                struct_definition.size_in_bytes()
            ), '"structure size must be consistent"') + get_line_ending(efi_type))
            out.write("" + get_line_ending(efi_type))
            pass

        out.write("// Schema-defined knobs" + get_line_ending(efi_type))
        for knob in schema.knobs:
            out.write("// {} knob".format(knob.name) + get_line_ending(efi_type))
            if knob.help != "":
                out.write("// {}".format(knob.help) + get_line_ending(efi_type))

            out.write("" + get_line_ending(efi_type))
            for subknob in knob.subknobs:
                if subknob.leaf:
                    define_name = subknob.name.replace('[', '_').replace(']', '_').replace('.', '__')
                    if subknob.min != subknob.format.min:
                        out.write("#define KNOB__{}__MIN {}".format(
                            define_name,
                            subknob.format.object_to_string(subknob.min, format_options)) + get_line_ending(efi_type))
                    if subknob.max != subknob.format.max:
                        out.write("#define KNOB__{}__MAX {}".format(
                            define_name,
                            subknob.format.object_to_string(subknob.max, format_options)) + get_line_ending(efi_type))

            out.write("" + get_line_ending(efi_type))
            out.write("// Get the current value of the {} knob".format(knob.name) + get_line_ending(efi_type))
            out.write("{} {}{}();".format(
                get_type_string(knob.format.c_type, efi_type),
                naming_convention_filter("config_get_",
                                         False,
                                         efi_type),
                knob.name))
            out.write("" + get_line_ending(efi_type))

            # no concept of setting config variables in UEFI
            if not efi_type:
                out.write("#ifdef CONFIG_SET_VARIABLES" + get_line_ending(efi_type))
                out.write("// Set the current value of the {} knob".format(knob.name) + get_line_ending(efi_type))
                out.write("{} config_set_{}({} value);".format(
                    get_type_string('bool', efi_type),
                    knob.name,
                    get_type_string(knob.format.c_type, efi_type),
                ) + get_line_ending(efi_type))
                out.write("#endif // CONFIG_SET_VARIABLES" + get_line_ending(efi_type))
                out.write("" + get_line_ending(efi_type))
            pass

        out.write("" + get_line_ending(efi_type))
        out.write("typedef enum {" + get_line_ending(efi_type))
        for knob in schema.knobs:
            out.write(get_spacing_string(efi_type) + "KNOB_{},".format(knob.name) + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type) + "KNOB_MAX" + get_line_ending(efi_type))
        out.write("}" + " {};".format(naming_convention_filter("knob_t", True, efi_type)) + get_line_ending(efi_type))
        out.write("" + get_line_ending(efi_type))
        # UEFI already defines EFI_GUID
        if not efi_type:
            out.write("typedef struct {" + get_line_ending(efi_type))
            out.write("    unsigned long  Data1;" + get_line_ending(efi_type))
            out.write("    unsigned short Data2;" + get_line_ending(efi_type))
            out.write("    unsigned short Data3;" + get_line_ending(efi_type))
            out.write("    unsigned char  Data4[8];" + get_line_ending(efi_type))
            out.write("} config_guid_t;" + get_line_ending(efi_type))
        out.write("" + get_line_ending(efi_type))
        out.write("typedef struct {" + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type) + "{} {};".format(
            get_type_string("int", efi_type),
            naming_convention_filter("get_count", False, efi_type)
        ) + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type) + "{} {};".format(
            get_type_string("int", efi_type),
            naming_convention_filter("set_count", False, efi_type)
        ) + get_line_ending(efi_type))
        out.write("}" + " {};".format(
            naming_convention_filter("knob_statistics_t", True, efi_type)
        ) + get_line_ending(efi_type))
        out.write("" + get_line_ending(efi_type))
        out.write("typedef {} ({})({} {});".format(
            get_type_string('bool', efi_type),
            naming_convention_filter("knob_validation_fn", True, efi_type),
            get_type_string("const", efi_type),
            get_type_string("void*", efi_type)
        ) + get_line_ending(efi_type))
        out.write("" + get_line_ending(efi_type))
        out.write("typedef struct {" + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type) + "{} {};".format(
            naming_convention_filter("knob_t", True, efi_type),
            naming_convention_filter("knob", False, efi_type)
        ) + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type) + "{} {} {};".format(
            get_type_string("const", efi_type),
            get_type_string("void*", efi_type),
            naming_convention_filter("default_value_address", False, efi_type)
        ) + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type) + "{} {};".format(
            get_type_string("void*", efi_type),
            naming_convention_filter("cache_value_address", False, efi_type)
        ) + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type) + "{} {};".format(
            get_type_string('size_t', efi_type),
            naming_convention_filter("value_size", False, efi_type)
        ) + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type) + "{} {} {};".format(
            get_type_string("const", efi_type),
            get_type_string("char*", efi_type),
            naming_convention_filter("name", False, efi_type)
        ) + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type) + "{} {};".format(
            get_type_string('size_t', efi_type),
            naming_convention_filter("name_size", False, efi_type)
        ) + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type) + "{} {};".format(
            get_type_string("config_guid_t", efi_type),
            naming_convention_filter("vendor_namespace", False, efi_type)
        ) + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type) + "{} {};".format(
            get_type_string("int", efi_type),
            naming_convention_filter("attributes", False, efi_type)
        ) + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type) + "{} {};".format(
            naming_convention_filter("knob_statistics_t", True, efi_type),
            naming_convention_filter("statistics", False, efi_type)
        ) + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type) + "{} {};".format(
            naming_convention_filter("knob_validation_fn*", True, efi_type),
            naming_convention_filter("validator", False, efi_type)
        ) + get_line_ending(efi_type))
        out.write("}" + " {};".format(
            naming_convention_filter("knob_data_t", True, efi_type)
        ) + get_line_ending(efi_type))
        out.write("" + get_line_ending(efi_type))
        out.write("typedef struct {" + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type) + "{} {};".format(
            naming_convention_filter("knob_t", True, efi_type),
            naming_convention_filter("knob", False, efi_type)
        ) + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type) + "{} {};".format(
            get_type_string("void*", efi_type),
            naming_convention_filter("value", False, efi_type)
        ) + get_line_ending(efi_type))
        out.write("}" + " {};".format(
            naming_convention_filter("knob_override_t", True, efi_type)
        ) + get_line_ending(efi_type))
        out.write("" + get_line_ending(efi_type))
        out.write("typedef struct {" + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type) + "{}* {};".format(
            naming_convention_filter("knob_override_t", True, efi_type),
            naming_convention_filter("overrides", False, efi_type)
        ) + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type) + "{} {};".format(
            get_type_string('size_t', efi_type),
            naming_convention_filter("override_count", False, efi_type)
        ) + get_line_ending(efi_type))
        out.write("}" + " {};".format(
            naming_convention_filter("profile_t", True, efi_type)
        ) + get_line_ending(efi_type))
        out.write("" + get_line_ending(efi_type))
        out.write("#pragma pack(pop)")
        out.write("" + get_line_ending(efi_type))
        out.write(get_include_once_style(header_path, uefi=efi_type, header=False))


def format_guid(guid):
    u = uuid.UUID(guid)

    byte_sequence = u.fields[3].to_bytes(1, byteorder='big') + \
                    u.fields[4].to_bytes(1, byteorder='big') + \
                    u.fields[5].to_bytes(6, byteorder='big')

    return "{{{},{},{},{{{},{},{},{},{},{},{},{}}}}}".format(
        hex(u.fields[0]),
        hex(u.fields[1]),
        hex(u.fields[2]),
        hex(byte_sequence[0]),
        hex(byte_sequence[1]),
        hex(byte_sequence[2]),
        hex(byte_sequence[3]),
        hex(byte_sequence[4]),
        hex(byte_sequence[5]),
        hex(byte_sequence[6]),
        hex(byte_sequence[7]))


def generate_cached_implementation(schema, header_path, efi_type=False):
    with open(header_path, 'w', newline='') as out:
        out.write(get_include_once_style(header_path, uefi=efi_type, header=True))
        out.write("// The config public header must be included prior to this file")
        out.write("// Generated Header" + get_line_ending(efi_type))
        out.write("//  Script: {}".format(sys.argv[0]) + get_line_ending(efi_type))
        out.write("//  Schema: {}".format(schema.path) + get_line_ending(efi_type))
        out.write("" + get_line_ending(efi_type))

        out.write("typedef struct {" + get_line_ending(efi_type))
        for knob in schema.knobs:
            out.write(get_spacing_string(efi_type) + "{} {};".format(
                get_type_string(knob.format.c_type, efi_type),
                knob.name) + get_line_ending(efi_type))
        out.write("}" + " {};".format(
            naming_convention_filter("knob_values_t", True, efi_type)
        ) + get_line_ending(efi_type))
        out.write("" + get_line_ending(efi_type))

        format_options = VariableList.StringFormatOptions()
        format_options.c_format = True
        format_options.efi_format = efi_type

        out.write("{} {} g{} = ".format(
            get_type_string("const", efi_type),
            naming_convention_filter("knob_values_t", True, efi_type),
            naming_convention_filter("_knob_default_values", False, efi_type)
        ) + get_line_ending(efi_type) + "{" + get_line_ending(efi_type))
        for knob in schema.knobs:
            out.write(get_spacing_string(efi_type) + ".{}={},".format(
                knob.name,
                knob.format.object_to_string(knob.default, format_options)
            ) + get_line_ending(efi_type))
        out.write("};" + get_line_ending(efi_type))

        out.write("#ifdef CONFIG_INCLUDE_CACHE" + get_line_ending(efi_type))
        out.write("{} g{} = ".format(
            naming_convention_filter("knob_values_t", True, efi_type),
            naming_convention_filter("_knob_cached_values", False, efi_type)
        ) + get_line_ending(efi_type) + "{" + get_line_ending(efi_type))
        for knob in schema.knobs:
            out.write("    .{}={},".format(
                knob.name,
                knob.format.object_to_string(knob.default, format_options)
            ) + get_line_ending(efi_type))
        out.write("};" + get_line_ending(efi_type))
        # macro use of 'knob', leave alone
        out.write("#define CONFIG_CACHE_ADDRESS(knob) (&g{}.knob)".format(
            naming_convention_filter("_knob_cached_values", False, efi_type)
        ) + get_line_ending(efi_type))
        out.write("#else // CONFIG_INCLUDE_CACHE" + get_line_ending(efi_type))
        out.write("#define CONFIG_CACHE_ADDRESS({}) (NULL)".format(
            naming_convention_filter("knob", False, efi_type)
        ) + get_line_ending(efi_type))
        out.write("#endif // CONFIG_INCLUDE_CACHE" + get_line_ending(efi_type))
        out.write("" + get_line_ending(efi_type))

        for enum in schema.enums:
            lowest_value = enum.values[0].number
            highest_value = enum.values[0].number
            for value in enum.values:
                if value.number < lowest_value:
                    lowest_value = value.number
                if value.number > highest_value:
                    highest_value = value.number

            out.write("{} {}{}({} {})".format(
                get_type_string('bool', efi_type),
                naming_convention_filter("validate_enum_value_", False, efi_type),
                enum.name,
                enum.name,
                naming_convention_filter("value", False, efi_type)) + get_line_ending(efi_type))
            out.write("{" + get_line_ending(efi_type))

            if highest_value - lowest_value > len(enum.values):
                out.write(get_spacing_string(efi_type) + "switch ({}) ".format(
                    naming_convention_filter("value", False, efi_type)
                ) + get_line_ending(efi_type) + "{" + get_line_ending(efi_type))

                for value in enum.values:
                    out.write(get_spacing_string(efi_type, 2) + "case {}_{}: return {};".format(
                        enum.name,
                        value.name,
                        get_value_string('true', efi_type)) + get_line_ending(efi_type))
                out.write(get_spacing_string(efi_type) + "}" + get_line_ending(efi_type))
                out.write(get_spacing_string(efi_type) + "return {};".format(
                    get_value_string('false', efi_type)
                ) + get_line_ending(efi_type))
            else:
                out.write(get_spacing_string(efi_type) + "{} {} = ({}){};".format(
                    get_type_string("int", efi_type),
                    naming_convention_filter("numeric_value", False, efi_type),
                    get_type_string("int", efi_type),
                    naming_convention_filter("value", False, efi_type)
                ) + get_line_ending(efi_type))
                out.write(get_spacing_string(efi_type) + "if ({} < {}) return {};".format(
                    naming_convention_filter("numeric_value", False, efi_type),
                    lowest_value,
                    get_value_string('false', efi_type)) + get_line_ending(efi_type))
                out.write(get_spacing_string(efi_type) + "if ({} > {}) return {};".format(
                    naming_convention_filter("numeric_value", False, efi_type),
                    highest_value,
                    get_value_string('false', efi_type)) + get_line_ending(efi_type))
                for i in range(lowest_value, highest_value):
                    found = False
                    for value in enum.values:
                        if value.number == i:
                            found = True
                            break
                    if not found:
                        out.write(get_spacing_string(efi_type) + "if ({} == {}) return {};".format(
                            naming_convention_filter("numeric_value", False, efi_type),
                            i,
                            get_value_string('false', efi_type)) + get_line_ending(efi_type))
                out.write(get_spacing_string(efi_type) + "return {};".format(
                    get_value_string('true', efi_type)
                ) + get_line_ending(efi_type))
            out.write("}" + get_line_ending(efi_type))
            out.write("" + get_line_ending(efi_type))

        out.write("" + get_line_ending(efi_type))

        out.write("{} {}({} {} {})".format(
            get_type_string('bool', efi_type),
            naming_convention_filter("validate_knob_no_constraints", False, efi_type),
            get_type_string("const", efi_type),
            get_type_string("void*", efi_type),
            naming_convention_filter("buffer", False, efi_type)
        ) + get_line_ending(efi_type))
        out.write("{" + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type) + "({}){};".format(
            get_type_string("void", efi_type),
            naming_convention_filter("buffer", False, efi_type)
        ) + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type) + "return {};".format(
            get_value_string('true', efi_type)
        ) + get_line_ending(efi_type))
        out.write("}" + get_line_ending(efi_type))
        out.write("" + get_line_ending(efi_type))
        for knob in schema.knobs:
            constraint_present = False
            for subknob in knob.subknobs:
                if subknob.leaf:
                    if isinstance(subknob.format, VariableList.EnumFormat):
                        constraint_present = True
                    else:
                        if subknob.min != subknob.format.min:
                            constraint_present = True
                        if subknob.max != subknob.format.max:
                            constraint_present = True

            if constraint_present:
                out.write("{} {}{}({} {} {})".format(
                    get_type_string('bool', efi_type),
                    naming_convention_filter("validate_knob_content_", False, efi_type),
                    knob.name,
                    get_type_string("const", efi_type),
                    get_type_string("void*", efi_type),
                    naming_convention_filter("buffer", False, efi_type)) + get_line_ending(efi_type))
                out.write("{" + get_line_ending(efi_type))
                out.write(get_spacing_string(efi_type) + "{}* {} = ({}*){};".format(
                    get_type_string(knob.format.c_type, efi_type),
                    naming_convention_filter("value", False, efi_type),
                    get_type_string(knob.format.c_type, efi_type),
                    naming_convention_filter("buffer", False, efi_type)
                ) + get_line_ending(efi_type))

                for subknob in knob.subknobs:
                    if subknob.leaf:
                        path = subknob.name[len(knob.name):]
                        define_name = subknob.name.replace('[', '_').replace(']', '_').replace('.', '__')
                        if isinstance(subknob.format, VariableList.EnumFormat):
                            out.write(get_spacing_string(efi_type) + "if ( !{}{}( (*{}){} ) ) return {};".format(
                                naming_convention_filter("validate_enum_value_", False, efi_type),
                                subknob.format.name,
                                naming_convention_filter("value", False, efi_type),
                                path,
                                get_value_string('false', efi_type)) + get_line_ending(efi_type))
                        else:
                            if subknob.min != subknob.format.min:
                                out.write(get_spacing_string(efi_type))
                                out.write("if ( (*{}){} < KNOB__{}__MIN ) return {};".format(
                                    naming_convention_filter("value", False, efi_type),
                                    path,
                                    define_name,
                                    get_value_string('false', efi_type)) + get_line_ending(efi_type))
                            if subknob.max != subknob.format.max:
                                out.write(get_spacing_string(efi_type))
                                out.write("if ( (*{}){} > KNOB__{}__MAX ) return {};".format(
                                    naming_convention_filter("value", False, efi_type),
                                    path,
                                    define_name,
                                    get_value_string('false', efi_type)) + get_line_ending(efi_type))
                out.write(get_spacing_string(efi_type) + "return {};".format(
                    get_value_string('true', efi_type)
                ) + get_line_ending(efi_type))
                out.write("}" + get_line_ending(efi_type))
                out.write("" + get_line_ending(efi_type))
            else:
                out.write("#define {}{} {}".format(
                    naming_convention_filter("validate_knob_content_", False, efi_type),
                    knob.name,
                    naming_convention_filter("validate_knob_no_constraints", False, efi_type)
                ) + get_line_ending(efi_type))
                out.write("" + get_line_ending(efi_type))

        out.write("" + get_line_ending(efi_type))
        out.write("{} g{}[{}] = {{".format(
            naming_convention_filter("knob_data_t", True, efi_type),
            naming_convention_filter("_knob_data", False, efi_type),
            len(schema.knobs) + 1
        ) + get_line_ending(efi_type))
        for knob in schema.knobs:
            out.write(get_spacing_string(efi_type) + "{" + get_line_ending(efi_type))
            out.write(get_spacing_string(efi_type, 2) + "KNOB_{},".format(knob.name) + get_line_ending(efi_type))
            out.write(get_spacing_string(efi_type, 2) + "&g{}.{},".format(
                naming_convention_filter("_knob_default_values", False, efi_type),
                knob.name
            ) + get_line_ending(efi_type))
            out.write(get_spacing_string(efi_type, 2))
            out.write("CONFIG_CACHE_ADDRESS({}),".format(knob.name) + get_line_ending(efi_type))
            out.write(get_spacing_string(efi_type, 2))
            out.write("sizeof({}),".format(get_type_string(knob.format.c_type, efi_type)) + get_line_ending(efi_type))
            out.write(get_spacing_string(efi_type, 2))
            out.write("\"{}\",".format(knob.name) + get_line_ending(efi_type))
            out.write(get_spacing_string(efi_type, 2))
            out.write("{}, // Length of name (including NULL terminator)".format(
                len(knob.name) + 1
            ) + get_line_ending(efi_type))
            out.write(get_spacing_string(efi_type, 2))
            out.write("{}, // {}".format(format_guid(knob.namespace), knob.namespace) + get_line_ending(efi_type))
            out.write(get_spacing_string(efi_type, 2))
            out.write("{},".format(7) + get_line_ending(efi_type))
            out.write(get_spacing_string(efi_type, 2))
            out.write("{0, 0}," + get_line_ending(efi_type))
            out.write(get_spacing_string(efi_type, 2) + "&{}{}".format(
                naming_convention_filter("validate_knob_content_", False, efi_type),
                knob.name
            ) + get_line_ending(efi_type))
            out.write(get_spacing_string(efi_type) + "}," + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type) + "{" + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type, 2) + "KNOB_MAX," + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type, 2) + "NULL," + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type, 2) + "NULL," + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type, 2) + "0," + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type, 2) + "NULL," + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type, 2) + "0," + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type, 2))
        out.write("{0,0,0,{0,0,0,0,0,0,0,0}}," + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type, 2) + "0," + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type, 2) + "{0, 0}," + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type, 2) + "NULL")
        out.write(get_line_ending(efi_type) + get_spacing_string(efi_type) + "}" + get_line_ending(efi_type))
        out.write("};" + get_line_ending(efi_type))

        out.write("" + get_line_ending(efi_type))
        out.write("{} {}({} {});".format(
            get_type_string("void*", efi_type),
            naming_convention_filter("get_knob_value", False, efi_type),
            naming_convention_filter("knob_t", True, efi_type),
            naming_convention_filter("knob", False, efi_type)
        ) + get_line_ending(efi_type))
        out.write("" + get_line_ending(efi_type))
        # no concept of setting config variables in UEFI
        if not efi_type:
            out.write("#ifdef CONFIG_SET_VARIABLES" + get_line_ending(efi_type))
            out.write("{} set_knob_value(knob_t knob, void* value);".format(
                get_type_string('bool', efi_type)
            ) + get_line_ending(efi_type))
            out.write("#endif // CONFIG_SET_VARIABLES" + get_line_ending(efi_type))
            out.write("" + get_line_ending(efi_type))
        out.write("// Schema-defined knobs" + get_line_ending(efi_type))
        for knob in schema.knobs:
            out.write("// {} knob".format(knob.name) + get_line_ending(efi_type))
            if knob.help != "":
                out.write("// {}".format(knob.help) + get_line_ending(efi_type))

            out.write("// Get the current value of the {} knob".format(knob.name) + get_line_ending(efi_type))
            out.write("{} {}{}() {{".format(
                get_type_string(knob.format.c_type, efi_type),
                naming_convention_filter("config_get_", False, efi_type),
                knob.name
            ) + get_line_ending(efi_type))
            out.write(get_spacing_string(efi_type) + "return *(({}*){}(KNOB_{}));".format(
                get_type_string(knob.format.c_type, efi_type),
                naming_convention_filter("get_knob_value", False, efi_type),
                knob.name
            ) + get_line_ending(efi_type))
            out.write("}" + get_line_ending(efi_type))
            out.write("" + get_line_ending(efi_type))
            # no concept of setting config variables in UEFI
            if not efi_type:
                out.write("#ifdef CONFIG_SET_VARIABLES" + get_line_ending(efi_type))
                out.write("// Set the current value of the {} knob".format(knob.name) + get_line_ending(efi_type))
                out.write("{} config_set_{}({} value) {{".format(
                    get_type_string('bool', efi_type),
                    knob.name,
                    knob.format.c_type))
                out.write(get_spacing_string(efi_type) + "return set_knob_value(KNOB_{}, &value);".format(
                    knob.name
                ) + get_line_ending(efi_type))
                out.write("}" + get_line_ending(efi_type))
                out.write("#endif // CONFIG_SET_VARIABLES" + get_line_ending(efi_type))
                out.write("" + get_line_ending(efi_type))
            pass
        out.write(get_include_once_style(header_path, uefi=efi_type, header=False))


def generate_profiles(schema, profile_header_path, profile_paths, efi_type):
    with open(profile_header_path, 'w', newline='') as out:
        out.write(get_include_once_style(profile_header_path, uefi=efi_type, header=True))
        out.write("// The config public header must be included prior to this file")
        out.write("// Generated Header" + get_line_ending(efi_type))
        out.write("//  Script: {}".format(sys.argv[0]) + get_line_ending(efi_type))
        out.write("//  Schema: {}".format(schema.path) + get_line_ending(efi_type))
        for profile_path in profile_paths:
            out.write("//  Profile: {}".format(profile_path) + get_line_ending(efi_type))

        out.write("" + get_line_ending(efi_type))

        format_options = VariableList.StringFormatOptions()
        format_options.c_format = True
        format_options.efi_format = efi_type

        profiles = []
        for profile_path in profile_paths:
            base_name = os.path.splitext(os.path.basename(profile_path))[0]
            out.write("// Profile {}".format(base_name) + get_line_ending(efi_type))
            # Reset the schema to defaults
            for knob in schema.knobs:
                knob.value = None

            # Read the csv to override the values in the schema
            VariableList.read_csv(schema, profile_path)

            override_count = 0

            out.write("typedef struct {" + get_line_ending(efi_type))
            for knob in schema.knobs:
                if knob.value is not None:
                    override_count = override_count + 1
                    out.write(get_spacing_string(efi_type) + "{} {};".format(
                        knob.format.c_type,
                        knob.name), + get_line_ending(efi_type))
            out.write("}} {}{}{};".format(
                naming_convention_filter("profile_", True, efi_type),
                base_name,
                naming_convention_filter("_data_t", True, efi_type)
            ) + get_line_ending(efi_type))

            out.write("" + get_line_ending(efi_type))
            out.write("{}{}{} {}{}{} = {{".format(
                naming_convention_filter("profile_", True, efi_type),
                base_name,
                naming_convention_filter("_data_t", True, efi_type),
                naming_convention_filter("profile_", False, efi_type),
                base_name,
                naming_convention_filter("_data", False, efi_type)
            ) + get_line_ending(efi_type))
            for knob in schema.knobs:
                if knob.value is not None:
                    out.write("    .{}={},".format(
                        knob.name,
                        knob.format.object_to_string(knob.value, format_options)) + get_line_ending(efi_type))
            out.write("};" + get_line_ending(efi_type))
            out.write("" + get_line_ending(efi_type))
            out.write("#define PROFILE_{}_OVERRIDES".format(base_name.upper()) + get_line_ending(efi_type))
            out.write("#define PROFILE_{}_OVERRIDES_COUNT {}".format(
                base_name.upper(),
                override_count
            ) + get_line_ending(efi_type))
            out.write("{} {}{}{}[PROFILE_{}_OVERRIDES_COUNT + 1] = {{".format(
                naming_convention_filter("knob_override_t", True, efi_type),
                naming_convention_filter("profile_", False, efi_type),
                base_name,
                naming_convention_filter("_overrides", False, efi_type),
                base_name.upper()
            ) + get_line_ending(efi_type))

            for knob in schema.knobs:
                if knob.value is not None:
                    out.write(get_spacing_string(efi_type) + "{" + get_line_ending(efi_type))
                    out.write(get_spacing_string(efi_type, 2) + ".{} = KNOB_{},".format(
                        naming_convention_filter("knob", False, efi_type),
                        knob.name
                    ) + get_line_ending(efi_type))
                    out.write(get_spacing_string(efi_type, 2) + ".{} = &{}{}{}.{},".format(
                        naming_convention_filter("value", False, efi_type),
                        naming_convention_filter("profile_", False, efi_type),
                        base_name,
                        naming_convention_filter("_data", False, efi_type),
                        knob.name
                    ) + get_line_ending(efi_type))
                    out.write(get_spacing_string(efi_type) + "}," + get_line_ending(efi_type))

            out.write(get_spacing_string(efi_type) + "{" + get_line_ending(efi_type))
            out.write(get_spacing_string(efi_type, 2) + ".{} = KNOB_MAX,".format(
                naming_convention_filter("knob", False, efi_type)
            ) + get_line_ending(efi_type))
            out.write(get_spacing_string(efi_type, 2) + ".{} = NULL,".format(
                naming_convention_filter("value", False, efi_type)
            ) + get_line_ending(efi_type))
            out.write(get_spacing_string(efi_type) + "}" + get_line_ending(efi_type))
            out.write("};" + get_line_ending(efi_type))
            out.write("" + get_line_ending(efi_type))

            profiles.append((base_name, override_count))
        out.write("" + get_line_ending(efi_type))
        out.write("#define PROFILE_COUNT {}".format(len(profiles)) + get_line_ending(efi_type))
        out.write("{} {}[PROFILE_COUNT + 1] = ".format(
            naming_convention_filter("profile_t", True, efi_type),
            naming_convention_filter("profiles", False, efi_type)
        ) + get_line_ending(efi_type) + "{" + get_line_ending(efi_type))
        for (profile, override_count) in profiles:
            out.write(get_spacing_string(efi_type) + "{" + get_line_ending(efi_type))
            out.write(get_spacing_string(efi_type, 2) + ".{} = {}{}{},".format(
                naming_convention_filter("overrides", False, efi_type),
                naming_convention_filter("profile_", False, efi_type),
                profile,
                naming_convention_filter("_overrides", False, efi_type)
            ) + get_line_ending(efi_type))
            out.write(get_spacing_string(efi_type, 2) + ".{} = {},".format(
                naming_convention_filter("override_count", False, efi_type),
                override_count
            ) + get_line_ending(efi_type))
            out.write(get_spacing_string(efi_type) + "}," + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type) + "{" + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type, 2) + ".{} = NULL,".format(
            naming_convention_filter("overrides", False, efi_type)
        ) + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type, 2) + ".{} = 0,".format(
            naming_convention_filter("override_count", False, efi_type)
        ) + get_line_ending(efi_type))
        out.write(get_spacing_string(efi_type) + "}" + get_line_ending(efi_type))
        out.write("};" + get_line_ending(efi_type))
        out.write(get_include_once_style(profile_header_path, uefi=efi_type, header=False))


def generate_sources(schema, public_header, service_header, efi_types):
    generate_public_header(schema, public_header, efi_types)
    generate_cached_implementation(schema, service_header, efi_types)


def usage():
    print("Commands:\n")
    print("  generateheader <schema.xml> <public_header.h> <service_header.h> [<profile_header.h> <profile.csv>...]")
    print("")
    print("schema.xml : An XML with the definition of a set of known")
    print("             UEFI variables ('knobs') and types to interpret them")


def main():
    if len(sys.argv) < 2:
        usage()
        sys.stderr.write('Must provide a command.\n')
        sys.exit(1)
        return

    if sys.argv[1].lower() == "generateheader" or sys.argv[1].lower() == "generateheader_efi":
        if len(sys.argv) < 5:
            usage()
            sys.stderr.write('Invalid number of arguments.\n')
            sys.exit(1)
            return

        efi_types = sys.argv[1].lower() == "generateheader_efi"

        schema_path = sys.argv[2]
        header_path = sys.argv[3]
        service_path = sys.argv[4]

        # Load the schema
        schema = VariableList.Schema.load(schema_path)

        generate_sources(schema, header_path, service_path, efi_types)

        if len(sys.argv) >= 6:
            profile_header_path = sys.argv[5]
            profile_paths = sys.argv[6:]

            generate_profiles(schema, profile_header_path, profile_paths, efi_types)
        return 0


if __name__ == '__main__':
    sys.exit(main())
#!/usr/bin/env python3
#
#    Script to generate WinRT C stubs for Wine from a compiled IDL file.
#    Example usage: ./WinRT_Gen.py -i ./windows.foundation.h -n IVectorView_HSTRING
#
#    Copyright (C) 2022 Bernhard Kölbl
#
#    This library is free software; you can redistribute it and/or
#    modify it under the terms of the GNU Lesser General Public
#    License as published by the Free Software Foundation; either
#    version 2.1 of the License, or (at your option) any later version.
#
#    This library is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public
#    License along with this library; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#

import argparse
import re

def main():
    parser = argparse.ArgumentParser(description='Generate stubbed C interfaces from generated WinRT headers.')
    parser.add_argument('-i', '--input', type=argparse.FileType('r'), help='The generated header by Widl.', required=True)
    parser.add_argument('-n', '--interface_name', type=str, help='Name of the interface to stub.', required=True)
    args = parser.parse_args()

    print('Stubbing interface "' + args.interface_name + '" from header "' + args.input.name + '".')

    iface_name = args.interface_name
    full_iface_name = ''
    vtbl_name = iface_name + 'Vtbl'
    full_vtbl_name = ''

    print('Searching for define of ' + vtbl_name)

    header = args.input
    for line in header:
        if vtbl_name in line:
            #print(line)
            full_vtbl_name = re.findall("__\w+Vtbl", line)[0]
            full_iface_name = full_vtbl_name.replace('Vtbl', '')
            break

    if not full_vtbl_name or not full_iface_name:
        print('Error: Full vtbl or iface name not found!')
        return

    #print(full_iface_name)
    search_text = 'typedef struct ' + full_vtbl_name
    print('Searching Vtbl -> "' + search_text + '"')

    output_file = open(iface_name + '.winrtstub', 'w+')
    header.seek(0)
    copy_line = False

    #Copy vtbl from header file to dst file.
    for num,line in enumerate(header, 1):
        if search_text in line:
            print("Found Vtbl in line " + str(num))
            copy_line = True
        if copy_line:
            output_file.write(line)
        if copy_line and '}' in line:
            copy_line = False
            break

    header.close()

    #Create class object name from the interface name.
    class_obj_name = iface_name
    class_obj_name = re.sub(r"^I|(_)I", r"\1", class_obj_name)
    class_obj_name = re.sub(r"([a-z])()([A-Z])", r"\1_\3", class_obj_name)
    class_obj_name = class_obj_name.lower()
    #print(class_obj_name)

    class_obj_definition = '''struct {struct_type}
{{
    {interface} {interface}_iface;
    LONG ref;
}};'''.format(struct_type=class_obj_name, interface=iface_name)

    #print(class_obj_definition)

    #Inner content of vtbl -> functions and comments.
    vtbl_function_list = []

    output_file.seek(0)

    #Generate vtble function names from imported vtbl and put it in the list.
    for line in output_file:
        #Matches function pointer from copied header vtbl.
        match = re.match(r"\s*[A-Z]+ \(STDMETHODCALLTYPE \*([\w+]+)\)\(", line)
        if match:
            #print(class_obj_name + '_' + match.group(1))
            #Put class obj name in front of function name.
            vtbl_function_list.append(class_obj_name + '_' + match.group(1))
            continue
        #Matches /*** IIface methods ***/ comment.
        match = re.match(r"\s+(/\*{3}\s.*\s\*{3}\/)", line)
        if match:
            #print(match.group(1))
            vtbl_function_list.append(match.group(1))
            continue

    vtbl_function_str = ''

    #Put newlines, commas or both, depending on where in the function is in the list.
    for x in vtbl_function_list:
        if x == vtbl_function_list[-1]:
            vtbl_function_str = vtbl_function_str + '    ' + x
        elif x.startswith("/*"):
            vtbl_function_str = vtbl_function_str + '    ' + x + '\n'
        else:
            vtbl_function_str = vtbl_function_str + '    ' + x + ',\n'

    #print(vtbl_function_str)

    vtbl_definition = '''static const struct {struct_type} {struct_name} =
{{
{functions}
}};'''.format(struct_type=vtbl_name, struct_name=class_obj_name+'_vtbl', functions=vtbl_function_str) #Note: {functions} are already tabbed.

    #print(vtbl_definition)

    impl_from_definition = '''static inline struct {impl_struct_type} *impl_from_{iface_name}({iface_name} *iface)
{{
    return CONTAINING_RECORD(iface, struct {impl_struct_type}, {iface_name}_iface);
}}'''.format(impl_struct_type=class_obj_name, iface_name=iface_name)

    #print(impl_from_definition)

    output_file.seek(0)

    functions_list = []
    function = ''

    #Create list of function definitions.
    for line in output_file:
        #Matches function return value and name from header.
        tmp = ''
        match = re.match(r"(\s+)([A-Z]+ )\(([A-Z]+) \*(\w+)\)\([\n]", line)
        if match:
            function = re.sub(r"(\s+)([A-Z]+ )\(([A-Z]+) \*(\w+)\)\([\n]", r"\2\3 " + class_obj_name + r"_\4(", line)
            #print(function)
        #Matches any line containing a function parameter, apart from the last.
        match = re.match(r"(\ +)((\w+) \**(\w+,))[\n]", line)
        if match:
            tmp = re.sub(r"(\ +)((\w+) \**(\w+,))[\n]", r"\2 ", line)
            #Next line generates the short versions of for example
            #__FIMapView_2_HSTRING___FIVectorView_1_HSTRING -> IMapView_HSTRING_IVectorView_HSTRING
            #__x_ABI_CWindows_CMedia_CSpeechRecognition_CISpeechRecognitionResult -> ISpeechRecognitionResult
            #__FIVectorView_1_Windows__CMedia__CSpeechRecognition__CSpeechRecognitionResult -> IVectorView_SpeechRecognitionResult
            function = function + re.sub(r"([1-9]_)|(__F)|([A-Za-z]+__C)|(__x_ABI_|([A-Za-z]+_C))", r"", tmp)
        #Matches last line containing a parameter.
        match = re.match(r"(\ +)((\w+) \**\w+\));", line)
        if match:
            tmp = re.sub(r"(\ +)((\w+) \**\w+\));", r"\2", line)
            #Next line generates the short versions of for example
            #__FIMapView_2_HSTRING___FIVectorView_1_HSTRING -> IMapView_HSTRING_IVectorView_HSTRING
            #__x_ABI_CWindows_CMedia_CSpeechRecognition_CISpeechRecognitionResult -> ISpeechRecognitionResult
            #__FIVectorView_1_Windows__CMedia__CSpeechRecognition__CSpeechRecognitionResult -> IVectorView_SpeechRecognitionResult
            function = function + re.sub(r"([1-9]_)|(__F)|([A-Za-z]+__C)|(__x_ABI_|([A-Za-z]+_C))", r"", tmp)
            function = re.sub(r"This", r"iface", function) #Replace This with iface
            function = function + "{\n    FIXME(\"iface %p stub!\\n\", iface);\n    return E_NOTIMPL;\n}"
            functions_list.append(function)
            #print(function)


    functions_str = ''

    for x in functions_list:
        if x == functions_list[-1]:
            functions_str = functions_str + x
        else:
            functions_str = functions_str + x + '\n\n'

    create_fun_definition = '''
static HRESULT STDMETHODCALLTYPE {class_obj_name}_create({interface} **out)
{{
    struct {class_obj_name} *impl;

    TRACE("out %p.\\n", out);

    if (!(impl = calloc(1, sizeof(*impl))))
    {{
        *out = NULL;
        return E_OUTOFMEMORY;
    }}

    impl->{interface}_iface.lpVtbl = &{class_obj_name}_vtbl;
    impl->ref = 1;

    *out = &impl->{interface}_iface;
    return S_OK;
}}'''.format(class_obj_name=class_obj_name, interface=iface_name)

    final_definition = '''{class_obj_definition}

{impl_from_definition}

{functions_definition}

{vtbl_definition}

{create_fun_definition}'''.format(class_obj_definition=class_obj_definition, impl_from_definition=impl_from_definition, functions_definition=functions_str, vtbl_definition=vtbl_definition, create_fun_definition=create_fun_definition)


    output_file.seek(0)
    output_file.write(final_definition)
    output_file.close()

    print("Generation done!~")


if __name__ == '__main__':
    main()

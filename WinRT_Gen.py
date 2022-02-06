#
# Script to generate WinRT C stubs for Wine from the compiled IDL files.
#
import argparse
import re

def main():
    parser = argparse.ArgumentParser(description='Generate stubbed C interfaces from generated WinRT headers.')
    parser.add_argument('-i', '--input', type=argparse.FileType('r'), help='The generated header by Widl.')
    parser.add_argument('-n', '--interface_name', type=str, help='Name of the interface to stub.')
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

    for line in header:
        if search_text in line:
            copy_line = True
        if copy_line:
            output_file.write(line)
        if '}' in line:
            copy_line = False

    header.close()

    class_obj_name = re.sub(r"([a-z])()([A-Z])", r"\1_\3", iface_name)
    class_obj_name = re.sub(r"^I|(_)I", r"\1", class_obj_name)
    class_obj_name = class_obj_name.lower()
    #print(class_obj_name)

    class_obj_definition = '''struct {struct_type}
{{
    {interface} {interface}_iface;
    LONG ref;
}};'''.format(struct_type=class_obj_name, interface=iface_name)

    #print(class_obj_definition)

    vtbl_function_list = []

    output_file.seek(0)

    for line in output_file:
        match = re.match(r"\s*[A-Z]+ \(STDMETHODCALLTYPE \*([\w+]+)\)\(", line)
        if match:
            #print(class_obj_name + '_' + match.group(1))
            vtbl_function_list.append(class_obj_name + '_' + match.group(1))
            continue
        match = re.match(r"\s+(/\*{3}\s.*\s\*{3}\/)", line)
        if match:
            #print(match.group(1))
            vtbl_function_list.append(match.group(1))
            continue

    vtbl_function_str = ''

    for x in vtbl_function_list:
        if x == vtbl_function_list[-1]:
            vtbl_function_str = vtbl_function_str + '    ' + x
        elif x.startswith("/*"):
            vtbl_function_str = vtbl_function_str + '    ' + x + '\n'
        else:
            vtbl_function_str = vtbl_function_str + '    ' + x + ',\n'

    #print(vtbl_function_str)

    vtbl_definition = '''static const struct {struct_type} {struct_name}
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

    for line in output_file:
        match = re.match(r"(\s+)([A-Z]+ )\(([A-Z]+) \*(\w+)\)\([\n]", line)
        if match:
            function = re.sub(r"(\s+)([A-Z]+ )\(([A-Z]+) \*(\w+)\)\([\n]", r"\2\3 " + class_obj_name + r"_\4(", line)
        match = re.match(r"(\ +)((\w+) \**(\w+,))[\n]", line)
        if match:
            tmp = re.sub(r"(\ +)((\w+) \**(\w+,))[\n]", r"\2 ", line)
            function = function + tmp
        match = re.match(r"(\ +)((\w+) \**\w+\));", line)
        if match:
            function = function + re.sub(r"(\ +)((\w+) \**\w+\));", r"\2", line)
            function = re.sub(r"__x_ABI_C\w+_C(\w+)( \**\w+)", r"\1\2", function) # Make eg __x_ABI_CWindows_CMedia_CSpeechRecognition_CISpeechRecognitionResult to ISpeechRecognitionResult
            function = re.sub(r"(\w+)(I[a-zA-Z]+)(\w+)__C(\w+)( \**\w+)", r"\2_\4\5", function) #Make eg __FIVectorView_1_Windows__CMedia__CSpeechRecognition__CSpeechRecognitionResult to IVectorView_SpeechRecognitionResult
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
static HRESULT STDMETHODCALLTYPE {class_obj_name}_create({interface} *out)
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

    print("Generation done!")


if __name__ == '__main__':
    main()

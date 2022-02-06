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

    print('Looking for ' + vtbl_name)

    header = args.input
    for line in header:
        if vtbl_name in line:
            print(line)
            full_vtbl_name = re.findall("__\w+Vtbl", line)[0]
            full_iface_name = full_vtbl_name.replace('Vtbl', '')
            break

    if not full_vtbl_name or not full_iface_name:
        print('Error: Full vtbl or iface name not found!')
        return

    print(full_iface_name)
    search_text = 'typedef struct ' + full_vtbl_name
    print('Searching for "' + search_text + '"')

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
    class_obj_name = re.sub(r"I", r"", class_obj_name).lower()
    print(class_obj_name)

    class_obj_defition = '''
struct {struct_type}
{{
    {interface} {interface}_iface;
    LONG ref;
}};'''.format(struct_type=class_obj_name, interface=iface_name)

    print(class_obj_defition)

    vtbl_function_list = []

    output_file.seek(0)

    for line in output_file:
        match = re.match(r"\s*[A-Z]+ \(STDMETHODCALLTYPE \*([\w+]+)\)\(", line)
        if match:
            print(class_obj_name + '_' + match.group(1))
            vtbl_function_list.append(class_obj_name + '_' + match.group(1))
            continue
        match = re.match(r"\s+(/\*{3}\s.*\s\*{3}\/)", line)
        if match:
            print(match.group(1))
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

    print(vtbl_function_str)

    vtbl_defition = '''
static const struct {struct_type} {struct_name}
{{
{functions}
}};'''.format(struct_type=vtbl_name, struct_name=class_obj_name+'_vtbl', functions=vtbl_function_str)

    print(vtbl_defition)

if __name__ == '__main__':
    main()

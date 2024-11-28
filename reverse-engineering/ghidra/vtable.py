# The idea here is to build a data type to use as a "container" for
# the virtual table of a given class. Select the region with the
# pointers to the virtual functions, having as a constraint that a
# label of the form "<Namespace>::<Class>::vtable" is at the start of it.
#
# Last update 2024-11-28
#
# @author Gianluca Pacchiella (https://github.com/gipi/ghidra_scripts)
# @category C++
# @keybinding SHIFT-V
# @menupath
# @toolbar
import logging

from ghidra.program.model.data import (
    StructureDataType,
    IntegerDataType,
    DataTypeConflictHandler,
    PointerDataType,
    FunctionDefinitionDataType,
    CategoryPath,
    DataTypePath,
    Undefined,
    Undefined4DataType,
    Undefined8DataType,
)

from ghidra.program.database.data import (
	FunctionDefinitionDB,
    PointerDB
)

from ghidra.util.task import ConsoleTaskMonitor

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel("INFO")

POINTER_SIZE = currentProgram.defaultPointerSize

def get_or_create_function(addr):
    function = getFunctionAt(addr)
    if function is None:
        logger.info("no function at {}, creating right now!".format(addr))
        function = createFunction(addr, None)  # use default name
    return function


def get_or_create_virtual_function(addr):
    if addr is None or addr == toAddr(0):
        logger.debug("skipping nullptr".format(addr))
        return None
    function = get_or_create_function(addr)
    name = function.getName()
    if name == "pure_virtual" or name == "__cxa_pure_virtual":
        logger.info("ignoring {} at {}".format(name, addr))
        return None
    return function


def deref_to_address(addr):
    references = getReferencesFrom(addr)
    assert len(references) <= 1
    if len(references) == 0:
        return None
    return references[0].getToAddress()


def create_pointer_data_if_untyped(addr):
    data = getDataContaining(addr)
    if (data is None or not data.isDefined() or Undefined.isUndefined(data.getDataType())):
        clearListing(addr)
        createData(addr, PointerDataType.dataType)


def build_and_add_vtable_struct(class_name, start_addr, count, cat_path):
    data_type_manager = currentProgram.getDataTypeManager()
    vtable_struct_name = "{}_vtable".format(class_name)

    logger.info("building struct named {}/{}".format(cat_path.getPath(), vtable_struct_name))
    structure = StructureDataType(cat_path, vtable_struct_name, 0)

    func_defs = []
    for index in range(count):
        logger.debug(" index: {}".format(index))
        address = start_addr.add(index * POINTER_SIZE)
        create_pointer_data_if_untyped(address)
        function_address = deref_to_address(address)
        function = get_or_create_virtual_function(function_address)

        if function is None:
            logger.info("skipping {}".format(address))
            structure.insertAtOffset(
                index * POINTER_SIZE, Undefined4DataType.dataType if POINTER_SIZE == 4 else Undefined8DataType.dataType, POINTER_SIZE, "pure_virtual", ""
            )
            continue

        function_name = function.getName()

        # if it's a function with an already defined Namespace don't change that
        if function.getParentNamespace().isGlobal():
            # set the right Namespace and the __thiscall convention
            logger.info("setting namespace for {}".format(function_name))
            namespace = getNamespace(None, class_name)
            function.setParentNamespace(namespace)

        # function.setCallingConvention('__thiscall')
        func_def = FunctionDefinitionDataType(function, False)
        func_def.setCategoryPath(cat_path)
        has_param = len(function.parameters) > 0
        if has_param:
            func_def.name += "("
        for param in function.parameters[:-1]:
            func_def.name += param.dataType.name + ","
        if has_param:
            func_def.name += function.parameters[-1].dataType.name
            func_def.name += ")"

        logger.debug(" with signature: {}".format(func_def))

        func_def_ptr = PointerDataType(func_def)

        # we replace all the things since they are generated automagically anyway
        logger.debug("Replacing {}".format(func_def))
        func_def = data_type_manager.addDataType(func_def, DataTypeConflictHandler.REPLACE_HANDLER)
        func_def_ptr = data_type_manager.addDataType(func_def_ptr, DataTypeConflictHandler.REPLACE_HANDLER)

        func_defs.append(func_def)
        func_defs.append(func_def_ptr)

        structure.insertAtOffset(
            index * POINTER_SIZE,
            func_def_ptr,
            POINTER_SIZE,
            function_name,
            "",
        )

    logger.info("Replacing {}".format(structure.getName()))
    data_type_manager.addDataType(structure, DataTypeConflictHandler.REPLACE_HANDLER)
    data_type_manager.addDataType(PointerDataType(structure), DataTypeConflictHandler.REPLACE_HANDLER)

    cat = data_type_manager.getCategory(cat_path)
    if cat != None:
        logger.debug("deleting old function definitions in category {}".format(cat_path.getPath()))
        monitor = ConsoleTaskMonitor()
        for data_type in cat.getDataTypes():
            if data_type not in func_defs and (isinstance(data_type, FunctionDefinitionDB) or (
                isinstance(data_type, PointerDB) and isinstance(data_type.getDataType(), FunctionDefinitionDB))):
                logger.debug("removing {}".format(data_type.name))
                cat.remove(data_type, monitor)
    
    return structure


def set_vtable_datatype(categorypath, class_name, structure):
    path = "{}/{}".format(categorypath, class_name)
    class_type = currentProgram.getDataTypeManager().getDataType(path)

    if class_type is None or class_type.isZeroLength():
        raise ValueError("You must define the class '{}' with '_vtable' before".format(class_name))

    field = class_type.getComponent(0)
    field_name = field.getFieldName()

    if field_name != "_vtable":
        raise ValueError("I was expecting the first field to be named '_vtable'")

    logger.info("set vtable as a pointer to {}".format(structure.getName()))
    field.setDataType(PointerDataType(structure))


def main():
    startAddress = currentSelection.getFirstRange().getMinAddress()
    count = currentSelection.getFirstRange().getLength() / POINTER_SIZE

    sym = getSymbolAt(startAddress)

    if sym is None or sym.getName() != "vtable" or sym.isGlobal():
        raise ValueError(
            "I was expecting a label here indicating the class Namespace, something like 'ClassName::vtable'")

    class_name = sym.getParentNamespace().getName()
    logger.info("class {}".format(class_name))
    if "::" in class_name:
        raise ValueError("Probably you want to handle manually this one: namespace '{}'".format(class_name))

    catnames = sym.getParentNamespace().getSymbol().getPath()
    catpath = ""

    for category in catnames:
        catpath = catpath + "/" + category

    categorypath = CategoryPath(catpath)
    build_and_add_vtable_struct(class_name, startAddress, count, categorypath)

    # set_vtable_datatype(class_name, structure)

main()

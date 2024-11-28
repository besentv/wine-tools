import os
import struct
import zlib
import sys
import uuid
import networkx as nx
import matplotlib.pyplot as plt
import pydot

def read8_at(data, pos):
    return struct.unpack("<B", data[pos])[0], pos + 1

def read16_at(data, pos):
    return struct.unpack("<H", data[pos:pos+2])[0], pos + 2

def read32_at(data, pos):
    return struct.unpack("<I", data[pos:pos+4])[0], pos + 4

def read32(data):
    return read32_at(data, 0)

def read_tag_at(data, pos, count):
    return data[pos:pos+count], pos + count

def read_tag_data(data, pos, tag : bytes):
    """
    Reads in the payload of a tag inside a extracted channelfile's datastream.

    Tags have the layout of:
    4 byte tag | 4 byte int payload length | payload

    Args:
        data: Array holding the channel file bytes.
        pos: Position to look for a tag in data.
        tag: Tag to look for.

    Returns:
        Tuple: (tag payload bytes as array, next position in data arg)

    """

    read_tag, next_pos = read_tag_at(data, pos, len(tag))

    if tag != read_tag:
        return None, pos

    size, next_pos = read32_at(data, next_pos)

    if size == 0:
        return None, pos

    pos = next_pos
    return data[pos:pos+size], pos + size


def decompress_cgr(path : str):
    if not path.endswith(".cgr"): return

    #TODO: Still very hacky.

    with open(path, "rb") as f:
        pos = 0
        data = f.read()

        # Returns the UUID of the unpacker channel
        _, pos = read_tag_data(data, pos, b"ACTF")

        # Zlib archive size
        size, pos = read_tag_data(data, pos, b"ZIOS")

        out_size, _ = read32(size)
        if out_size == None: return

        # Decompressed archive size
        size, pos = read_tag_data(data, pos, b"ZINS")

        in_size, _ = read32(size)
        if in_size == None: return

        # Archive data
        archive, pos = read_tag_data(data, pos, b"ZICB")
        print("decompressing " + path)

        output = zlib.decompress(archive, bufsize=out_size)
        with open(path + "_d", "wb+") as w:
            w.write(output)



#TODO: Improve dotfile generation code.
queue = []

def bfs(visited, graph, node): #function for BFS
  visited.append(node)
  queue.append(node)

  while queue:          # Creating loop to visit each node
    m = queue.pop(0) 
    print (m, end = " ") 

    if graph[m] is not None:
        for neighbour in graph[m]['links']:
          if neighbour not in visited and neighbour != 4294967295:
            visited.append(neighbour)
            queue.append(neighbour)

def to_dot(data : []):

    # Use this to get a node and all its children
    #bfs(expected_2, data, 2569)
    #bfs(expected_2, data, 1)

    for x in data:
        expected_2.append(x['index'])

    nodes = []
    edges = []
    labelDict = {}

    for x in expected_2:
        print (str(x))
        if data[x] is not None:
            nodes.append(x)
            for i in data[x]['links']:
                if i == 4294967295: continue
                edges.append((x,i))

    for x in data:
        if x is not None:
            index = x['index']
            if index in nodes:
                labelDict[index] = str(x['name']) + " (" + str(index) + ")"


    print_colors = ['red','blue','yellow','cyan']
    colors_e = [print_colors[i%4] for i in range(G.number_of_edges())]
    colors_n = [print_colors[i%4] for i in range(G.number_of_nodes())]

    with open("out3.dot", "w") as text_file:
        text_file.write("digraph G {\n")

        for i in range(len(nodes)):
            text_file.write("%d [label=\"%s\"]\n" % (nodes[i], labelDict[nodes[i]]))

        for i in range(len(edges)):
            aval = (*edges[i], colors_e[i])
            text_file.write("%d -> %d [color=\"%s\"]\n" % aval)

        text_file.write("}\n")


def visualize_cgr(path : str):
    with open(path, "rb") as f:
        pos = 0
        data = f.read()

        #Quest3D version
        _, pos = read_tag_data(data, pos, b"QVRS")

        #A3DG - Channel Group indication tag
        _, pos = read_tag_at(data, pos, len(b'A3DG'))

        #Some GUID
        _, pos = read_tag_data(data, pos, b"CGGG")

        #???
        _, pos = read_tag_data(data, pos, b"ENVR")

        #Unique channel count (skpping for now because 0 in test file)
        _, pos = read_tag_data(data, pos, b"CGUC")

        #Channel count
        tag_data, pos = read_tag_data(data, pos, b"CHCO")
        channel_count, _ = read32(tag_data)

        channels = [None] * channel_count

        for i in range(0, channel_count, 1):
            #Channel index
            next_pos = data.find(b"CHIX", pos)
            if next_pos == -1: break
            
            tag_data, pos = read_tag_data(data, next_pos, b"CHIX")
            channel_index, _ = read32(tag_data)
            if channel_index == -1: raise Exception("Not implemented")

            #Channel (UU)ID
            tag_data, pos = read_tag_data(data, pos, b"CHID")
            channel_uuid = uuid.UUID(bytes_le=tag_data)

            #Ignore tree count (Bool)?
            next_pos = data.find(b"CHIC", pos) #Skipping stray CHES tags
            tag_data, pos = read_tag_data(data, next_pos, b"CHIC")

            #Channel Name
            tag_data, pos = read_tag_data(data, pos, b"CHNA")

            channel_name = ""

            if tag_data is not None:
                channel_name = tag_data.decode("UTF-8").rstrip('\x00')

            #Interface Type
            tag_data, pos = read_tag_data(data, pos, b"CHIT")
            interface_type = 0
            if tag_data is not None:
                    interface_type, _ = read32(tag_data)

            tag_data, pos = read_tag_data(data, pos, b"CHES")
            if tag_data is not None:
                channel_name = tag_data.split(b'\0',1)[0].decode("UTF-8").rstrip('\x00')

            print(str(channel_index) + ":" + str(channel_uuid) + ":" + channel_name)

            #Channel link count
            next_pos = data.find(b"CHLC", pos)
            if next_pos == -1:
                raise Exception("Link Count not found for index " + str(channel_index))
            tag_data, pos = read_tag_data(data, next_pos, b"CHLC")
            if tag_data is None: raise Exception("Link Count not parsable")

            link_count, _ = read32(tag_data)
            channel_links = []

            for i in range(0, link_count, 1):
                #Link index (to node)
                tag_data, pos = read_tag_data(data, pos, b"CHLI")
                link_index, _ = read32(tag_data)

                #???
                _, pos = read_tag_data(data, pos, b"CHUL")

                #???
                _, pos = read_tag_data(data, pos, b"CHRP")

                print("    -> "+ str(link_index))

                channel_links.append(link_index)

            channel_entry = {
                'index' : channel_index,
                'name' : channel_name,
                'links' : channel_links
            }

            channels[channel_index] = channel_entry

        to_dot(channels)



def main():
    if len(sys.argv) < 2:
        raise Exception("Too few args. Usage: cgr.py CHANNELFILE.cgr")

    decompress_cgr(sys.argv[1])
    visualize_cgr(sys.argv[1] + "_d")


if __name__ == "__main__":
    main()

####################################################################
#                                                                  #
# THIS FILE IS PART OF THE pycollada LIBRARY SOURCE CODE.          #
# USE, DISTRIBUTION AND REPRODUCTION OF THIS LIBRARY SOURCE IS     #
# GOVERNED BY A BSD-STYLE SOURCE LICENSE INCLUDED WITH THIS SOURCE #
# IN 'COPYING'. PLEASE READ THESE TERMS BEFORE DISTRIBUTING.       #
#                                                                  #
# THE pycollada SOURCE CODE IS (C) COPYRIGHT 2011                  #
# by Jeff Terrace and contributors                                 #
#                                                                  #
####################################################################

"""Module for managing data sources defined in geometry tags."""

import numpy

from collada.common import DaeObject, E, tag
from collada.common import DaeIncompleteError, DaeBrokenRefError, DaeMalformedError
from collada.xmlutil import etree as ElementTree

class InputList(object):
    """Used for defining input sources to a geometry."""

    class Input:
        def __init__(self, offset, semantic, src, set=None):
            self.offset = offset
            self.semantic = semantic
            self.source = src
            self.set = set

    semantics = ["VERTEX", "NORMAL", "TEXCOORD", "TEXBINORMAL", "TEXTANGENT", "COLOR", "TANGENT", "BINORMAL"]

    def __init__(self):
        """Create an input list"""
        self.inputs = {}
        for s in self.semantics:
            self.inputs[s] = []

    def addInput(self, offset, semantic, src, set=None):
        """Add an input source to this input list.

        :param int offset:
          Offset for this source within the geometry's indices
        :param str semantic:
          The semantic for the input source. Currently supported options are:
            * VERTEX
            * NORMAL
            * TEXCOORD
            * TEXBINORMAL
            * TEXTANGENT
            * COLOR
            * TANGENT
            * BINORMAL
        :param str src:
          A string identifier of the form `#srcid` where `srcid` is a source
          within the geometry's :attr:`~collada.geometry.Geometry.sourceById` array.
        :param str set:
          Indicates a set number for the source. This is used, for example,
          when there are multiple texture coordinate sets.

        """
        if semantic not in self.semantics:
            raise DaeUnsupportedError("Unsupported semantic %s" % semantic)
        self.inputs[semantic].append(self.Input(offset, semantic, src, set))

    def getList(self):
        """Returns a list of tuples of the source in the form (offset, semantic, source, set)"""
        retlist = []
        for inplist in self.inputs.values():
            for inp in inplist:
                 retlist.append((inp.offset, inp.semantic, inp.source, inp.set))
        return retlist

    def __str__(self): return '<InputList>'
    def __repr__(self): return str(self)

class Source(DaeObject):
    """Abstract class for loading source arrays"""

    @staticmethod
    def load(collada, localscope, node):
        sourceid = node.get('id')
        arraynode = node.find(tag('float_array'))
        if not arraynode is None:
            return FloatSource.load(collada, localscope, node)

        arraynode = node.find(tag('IDREF_array'))
        if not arraynode is None:
            return IDRefSource.load(collada, localscope, node)

        arraynode = node.find(tag('Name_array'))
        if not arraynode is None:
            return NameSource.load(collada, localscope, node)

        if arraynode is None: raise DaeIncompleteError('No array found in source %s' % sourceid)


class FloatSource(Source):
    """Contains a source array of floats, as defined in the collada
    <float_array> inside a <source>.

    If ``f`` is an instance of :class:`collada.source.FloatSource`, then
    ``len(f)`` is the length of the shaped source. ``len(f)*len(f.components)``
    would give you the number of values in the source. ``f[i]`` is the i\ :sup:`th`
    item in the source array.
    """

    def __init__(self, id, data, components, xtype="",stride=0, xmlnode=None):
        """Create a float source instance.

        :param str id:
          A unique string identifier for the source
        :param numpy.array data:
          Numpy array (unshaped) with the source values
        :param tuple components:
          Tuple of strings describing the semantic of the data,
          e.g. ``('X','Y','Z')`` would cause :attr:`data` to be
          reshaped as ``(-1, 3)``
        :param str xtype:
          The type of the components, default is float but it could be float4x4
        :param int stride:
          The size of stride, default is automatic from number of components, but given for float4x4 matrices
        :param xmlnode:
          When loaded, the xmlnode it comes from.

        """

        self.id = id
        """The unique string identifier for the source"""
        self.data = data
        """Numpy array with the source values. This will be shaped as ``(-1,N)`` where ``N = len(self.components)``"""
        self.data.shape = (-1, len(components) )
        self.components = components
        """Tuple of strings describing the semantic of the data, e.g. ``('X','Y','Z')``"""
        self.ctype = xtype
        """Component Type, special for TRANSFORM without type"""
        self.stridelen = stride
        """Stride"""
        if self.ctype == "": #default
            if len(components) == 1 and components[0] == "TRANSFORM":
                self.ctype = "float4x4"
            else:
                ctype = "float"
        if self.stridelen == 0: #default
            if self.ctype == "float4x4":
                self.stridelen = 16
            else:
                self.stridelen = len(self.components)
        if xmlnode != None:
            self.xmlnode = xmlnode
            """ElementTree representation of the source."""
        else:
            self.data.shape = (-1,)
            txtdata = ' '.join(map(str, self.data.tolist() ))
            rawlen = len( self.data )
            self.data.shape = (-1, len(self.components) )
            acclen = len( self.data )
            sourcename = "%s-array"%self.id

            self.xmlnode = E.source(
                E.float_array(txtdata, count=str(rawlen), id=sourcename),
                E.technique_common(
                    E.accessor(
                        *[E.param(type=self.ctype, name=c) for c in self.components]
                    , **{'count':str(acclen), 'stride':str(self.stridelen), 'source':"#%s"%sourcename} )
                )
            , id=self.id )

    def __len__(self): return len(self.data)

    def __getitem__(self, i): return self.data[i]

    def save(self):
        """Saves the source back to :attr:`xmlnode`"""
        self.data.shape = (-1,)

        txtdata = ' '.join(map(lambda x: '%.7g'%x , self.data.tolist()))

        stridelen = self.stridelen
        if stridelen == 0:
            if self.ctype == "float4x4":
                stridelen = 16
            else:
                stridelen = len(self.components)

        rawlen = len( self.data )
        self.data.shape = (-1, len(self.components) )
        acclen = len( self.data )
        node = self.xmlnode.find(tag('float_array'))
        node.text = txtdata
        node.set('count', str(rawlen))
        node.set('id', self.id+'-array' )
        node = self.xmlnode.find('%s/%s'%(tag('technique_common'), tag('accessor')))
        node.clear()
        node.set('count', str(acclen))
        node.set('source', '#'+self.id+'-array')
        node.set('stride', str(stridelen))
        for c in self.components:
            if c is None:
                node.append(E.param(type=self.ctype))
            else:
                node.append(E.param(type=self.ctype, name=c))
        self.xmlnode.set('id', self.id )

    @staticmethod
    def load( collada, localscope, node ):
        sourceid = node.get('id')
        arraynode = node.find(tag('float_array'))
        if arraynode is None: raise DaeIncompleteError('No float_array in source node')
        if arraynode.text is None:
            data = numpy.array([], dtype=numpy.float32)
        else:
            try: data = numpy.fromstring(arraynode.text, dtype=numpy.float32, sep=' ')
            except ValueError: raise DaeMalformedError('Corrupted float array')
        data[numpy.isnan(data)] = 0

        stridelen = int(node.attrib.get('stride','0'))

        paramnodes = node.findall('%s/%s/%s'%(tag('technique_common'), tag('accessor'), tag('param')))
        if not paramnodes: raise DaeIncompleteError('No accessor info in source node')
        components = [ param.get('name') for param in paramnodes ]
        tcomponents = [ param.get('type') for param in paramnodes ]
        if len(tcomponents) > 0:
            xtype = tcomponents[0]
        else:
            xtype = "" # default
        if len(components) == 2 and components[0] == 'U' and components[1] == 'V':
            #U,V is used for "generic" arguments - convert to S,T
            components = ['S', 'T']
        if len(components) == 3 and components[0] == 'S' and components[1] == 'T' and components[2] == 'P':
            components = ['S', 'T']
            data.shape = (-1, 3)
            #remove 3d texcoord dimension because we don't support it
            #TODO
            data = numpy.array(zip(data[:,0], data[:,1]))
            data.shape = (-1)
        return FloatSource( sourceid, data, tuple(components), xtype=xtype, stride=stridelen, xmlnode=node )

    def __str__(self): return '<FloatSource size=%d>' % (len(self),)
    def __repr__(self): return str(self)


class IDRefSource(Source):
    """Contains a source array of ID references, as defined in the collada
    <IDREF_array> inside a <source>.

    If ``r`` is an instance of :class:`collada.source.IDRefSource`, then
    ``len(r)`` is the length of the shaped source. ``len(r)*len(r.components)``
    would give you the number of values in the source. ``r[i]`` is the i\ :sup:`th`
    item in the source array.

    """

    def __init__(self, id, data, components, xmlnode=None):
        """Create an id ref source instance.

        :param str id:
          A unique string identifier for the source
        :param numpy.array data:
          Numpy array (unshaped) with the source values
        :param tuple components:
          Tuple of strings describing the semantic of the data,
          e.g. ``('MORPH_TARGET')`` would cause :attr:`data` to be
          reshaped as ``(-1, 1)``
        :param xmlnode:
          When loaded, the xmlnode it comes from.

        """

        self.id = id
        """The unique string identifier for the source"""
        self.data = data
        """Numpy array with the source values. This will be shaped as ``(-1,N)`` where ``N = len(self.components)``"""
        self.data.shape = (-1, len(components) )
        self.components = components
        """Tuple of strings describing the semantic of the data, e.g. ``('MORPH_TARGET')``"""
        if xmlnode != None:
            self.xmlnode = xmlnode
            """ElementTree representation of the source."""
        else:
            self.data.shape = (-1,)
            txtdata = ' '.join(map(str, self.data.tolist() ))
            rawlen = len( self.data )
            self.data.shape = (-1, len(self.components) )
            acclen = len( self.data )
            stridelen = len(self.components)
            sourcename = "%s-array"%self.id

            self.xmlnode = E.source(
                E.IDREF_array(txtdata, count=str(rawlen), id=sourcename),
                E.technique_common(
                    E.accessor(
                        *[E.param(type='IDREF', name=c) for c in self.components]
                    , **{'count':str(acclen), 'stride':str(stridelen), 'source':sourcename})
                )
            , id=self.id )

    def __len__(self): return len(self.data)

    def __getitem__(self, i): return self.data[i][0] if len(self.data[i])==1 else self.data[i]

    def save(self):
        """Saves the source back to :attr:`xmlnode`"""
        self.data.shape = (-1,)
        txtdata = ' '.join(map(str, self.data.tolist() ))
        rawlen = len( self.data )
        self.data.shape = (-1, len(self.components) )
        acclen = len( self.data )

        node = self.xmlnode.find(tag('IDREF_array'))
        node.text = txtdata
        node.set('count', str(rawlen))
        node.set('id', self.id+'-array' )
        node = self.xmlnode.find('%s/%s'%(tag('technique_common'), tag('accessor')))
        node.clear()
        node.set('count', str(acclen))
        node.set('source', '#'+self.id+'-array')
        node.set('stride', str(len(self.components)))
        for c in self.components:
            node.append(E.param(type='IDREF', name=c))
        self.xmlnode.set('id', self.id )

    @staticmethod
    def load( collada, localscope, node ):
        sourceid = node.get('id')
        arraynode = node.find(tag('IDREF_array'))
        if arraynode is None: raise DaeIncompleteError('No IDREF_array in source node')
        if arraynode.text is None:
            values = []
        else:
            try: values = [v for v in arraynode.text.split()]
            except ValueError: raise DaeMalformedError('Corrupted IDREF array')
        data = numpy.array( values, dtype=numpy.string_ )
        paramnodes = node.findall('%s/%s/%s'%(tag('technique_common'), tag('accessor'), tag('param')))
        if not paramnodes: raise DaeIncompleteError('No accessor info in source node')
        components = [ param.get('name') for param in paramnodes ]
        return IDRefSource( sourceid, data, tuple(components), xmlnode=node )

    def __str__(self): return '<IDRefSource size=%d>' % (len(self),)
    def __repr__(self): return str(self)

class NameSource(Source):
    """Contains a source array of strings, as defined in the collada
    <Name_array> inside a <source>.

    If ``n`` is an instance of :class:`collada.source.NameSource`, then
    ``len(n)`` is the length of the shaped source. ``len(n)*len(n.components)``
    would give you the number of values in the source. ``n[i]`` is the i\ :sup:`th`
    item in the source array.

    """

    def __init__(self, id, data, components, xtype="IDREF", xmlnode=None):
        """Create a name source instance.

        :param str id:
          A unique string identifier for the source
        :param numpy.array data:
          Numpy array (unshaped) with the source values
        :param tuple components:
          Tuple of strings describing the semantic of the data,
          e.g. ``('JOINT')`` would cause :attr:`data` to be
          reshaped as ``(-1, 1)``
        :param str xtype:
          The type of the entities in the named source
        :param xmlnode:
          When loaded, the xmlnode it comes from.

        """

        self.id = id
        """The unique string identifier for the source"""
        self.type = xtype
        """The type of the entities mentioned, e.g. IDREF or Name"""
        if type(data) is list:
            data = numpy.array( data, dtype=numpy.string_ )
        self.data = data
        """Numpy array with the source values. This will be shaped as ``(-1,N)`` where ``N = len(self.components)``"""
        self.data.shape = (-1, len(components) )
        self.components = components
        """Tuple of strings describing the semantic of the data, e.g. ``('JOINT')``"""
        if xmlnode != None:
            self.xmlnode = xmlnode
            """ElementTree representation of the source."""
        else:
            self.data.shape = (-1,)
            txtdata = ' '.join(map(str, self.data.tolist() ))
            rawlen = len( self.data )
            self.data.shape = (-1, len(self.components) )
            acclen = len( self.data )
            stridelen = len(self.components)
            sourcename = "%s-array"%self.id

            self.xmlnode = E.source(
                E.Name_array(txtdata, count=str(rawlen), id=sourcename),
                E.technique_common(
                    E.accessor(
                        *[E.param(type='Name', name=c) for c in self.components]
                    , **{'count':str(acclen), 'stride':str(stridelen), 'source':sourcename})
                )
            , id=self.id )

    def __len__(self): return len(self.data)

    def __getitem__(self, i): return self.data[i][0] if len(self.data[i])==1 else self.data[i]

    def save(self):
        """Saves the source back to :attr:`xmlnode`"""
        self.data.shape = (-1,)
        txtdata = ' '.join(map(str, self.data.tolist() ))
        rawlen = len( self.data )
        self.data.shape = (-1, len(self.components) )
        acclen = len( self.data )

        node = self.xmlnode.find(tag('Name_array'))
        node.text = txtdata
        node.set('count', str(rawlen))
        node.set('id', self.id+'-array' )
        node = self.xmlnode.find('%s/%s'%(tag('technique_common'), tag('accessor')))
        node.clear()
        node.set('count', str(acclen))
        node.set('source', '#'+self.id+'-array')
        node.set('stride', str(len(self.components)))
        for c in self.components:
            node.append(E.param(type=self.type, name=c))
        self.xmlnode.set('id', self.id )

    @staticmethod
    def load( collada, localscope, node ):
        sourceid = node.get('id')
        arraynode = node.find(tag('Name_array'))
        if arraynode is None: raise DaeIncompleteError('No Name_array in source node')
        if arraynode.text is None:
            values = []
        else:
            try: values = [v for v in arraynode.text.split()]
            except ValueError: raise DaeMalformedError('Corrupted Name array')
        data = numpy.array( values, dtype=numpy.string_ )
        paramnodes = node.findall('%s/%s/%s'%(tag('technique_common'), tag('accessor'), tag('param')))
        if not paramnodes: raise DaeIncompleteError('No accessor info in source node')
        components = [ param.get('name') for param in paramnodes ]
        componenttypes = [ param.get('type','') for param in paramnodes ]
        if len(componenttypes) == 1:
            xtype = componenttypes[0]
        else:
            xtype = "IDREF"
        return NameSource( sourceid, data, tuple(components), xtype=xtype, xmlnode=node )

    def __str__(self): return '<NameSource size=%d>' % (len(self),)
    def __repr__(self): return str(self)

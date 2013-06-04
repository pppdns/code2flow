'''
The main logic goes here.
This is the base module which is then partially overwritten by the language chosen

There are three basic modules defined:
Graphs: which represent namespaces
Nodes:  which represent functions
Edges:  which represent function calls
'''

import abc
import copy
import importlib
import operator
import os
import re
import pdb
import pprint

from nesting import *

currentUID = 0

def generateEdges(nodes):
	'''
	When a function calls another function, that is an edge
	'''
	edges = []
	for node0 in nodes:
		for node1 in nodes:
			if DEBUG:
				print '"%s" links to "%s"?'%(node0.name,node1.name)
			if node0.linksTo(node1):
				if DEBUG:
					print "Edge created"
				edges.append(Edge(node0,node1))
	return edges

class Node(object):
	'''
	Nodes represent functions
	'''
	returnPattern = re.compile(r"\Wreturn\W",re.MULTILINE)

	namespaceBeforeDotPattern = re.compile(r'(?:[^\w\.]|\A)([\w\.]+)\.$',re.MULTILINE)

	def __init__(self,name,definitionString,source,parent,fullSource=None,characterPos=0,lineNumber=0,isFileRoot=False): #allow default characterPos, lineNumber for implicit nodes
		#basic vars
		self.name = name
		self.definitionString = definitionString
		self.source = source
		self.fullSource=fullSource or source
		self.parent = parent
		self.characterPos = characterPos
		self.lineNumber = lineNumber #The line number the definition is on
		self.isFileRoot = isFileRoot

		#generate the name patterns for other nodes to search for this one
		self.pattern = re.compile(r"(?:\W|\A)(%s)\s*\("%self.name,re.MULTILINE)  # The name pattern which is found by others eg. node()

		self.determineNodeType() # Init node, etc.

		self.sameScopePatterns = self.generateSameScopePatterns()  # The pattern to search for when the other node is in the same scope e.g. self.node()
		self.namespacePatterns = self.generateNamespacePatterns() # The pattern to search for with the namespace eg. Node.node()
		#pdb.set_trace()
		#just whether there are return statements or not
		self.returns = self.returnPattern.search(self.source.sourceString)

		#increment the identifier
		#Needed for the sake of a unique node name for graphviz
		global currentUID
		self.uid = currentUID
		currentUID += 1

		#Assume it is a leaf and a trunk until determined otherwise
		self.isLeaf = True #it calls nothing else
		self.isTrunk = True #nothing calls it



	def generateSameScopePatterns(self):
		return [re.compile(r"(?:\W|\A)%s\.%s\s*\("%(self.sameScopeKeyword,self.name),re.MULTILINE|re.DOTALL)]

	def generateNamespacePatterns(self):
		return [
			re.compile(r"(?:\W|\A)%s\s*\("%(self.getFullName()),re.MULTILINE|re.DOTALL)
			]


	def getFileGroup(self):
		return self.parent.getFileGroup()

	def getFileName(self):
		return self.parent.getFileName()

	def getNamespace(self):
		return self.parent.getNamespace()


	def determineNodeType(self):
		'''
		Dummy meant to be subclassed if we need this functionality
		'''
		self.isInitNode = False


	def getFullName(self):
		#if self.isFileRoot():
		#	return self.name
		#lse:
		namespace = self.getNamespace()
		if '/' in namespace:
			namespace = namespace.rsplit('/',1)[1]

		return namespace+'.'+self.name if namespace else self.name



	def contains(self,other):
		return other.linksTo(self)

	'''
	def setGroup(self,group):
		self.group = group
		self.thisPattern = re.compile(r"\Wthis\.%s\s*\("%self.name,re.MULTILINE)
		print r"\Wthis\.%s\s*\("%self.name
		self.nameSpacePattern = re.compile(r"\W%s\.%s\s*\("%(self.group.name,self.name),re.MULTILINE)
		print r"\W%s\.%s\s*\("%(self.group.name,self.name)
	'''

	def getUID(self):
		return 'node'+str(self.uid)

	def __str__(self):
		'''
		For printing to the DOT file
		'''
		attributes = {}

		attributes['label']="%d: %s"%(self.lineNumber,self.getFullName())
		attributes['shape']="rect"
		attributes['style']="rounded"
		#attributes['splines']='ortho'
		if self.isTrunk:
			attributes['style']+=',filled'
			attributes['fillcolor']='brown'
		elif self.isLeaf:
			attributes['style']+=',filled'
			attributes['fillcolor']='green'

		ret = self.getUID()
		if attributes:
			ret += ' [splines=ortho '
			for a in attributes:
				ret += '%s = "%s" '%(a,attributes[a])
			ret += ']'

		return ret

class Edge(object):
	'''
	Edges represent function calls
	'''
	def __init__(self,node0,node1):
		self.node0 = node0
		self.node1 = node1

		#When we draw the edge, we know the calling function is definitely not a leaf...
		#and the called function is definitely not a trunk
		node0.isLeaf = False
		node1.isTrunk = False

	def __str__(self):
		'''
		For printing to the DOT file
		'''
		ret = self.node0.getUID() + ' -> ' + self.node1.getUID()
		if self.node1.returns:
			ret += ' [color="blue" penwidth="2"]'
		return ret

	def hasEndNode(self,node1):
		return node1 == self.node1

	def hasStartNode(self,node0):
		return node0 == self.node0

class Group(object):
	'''
	Groups represent namespaces
	'''

	def __init__(self,name,source,fullSource=None,definitionString='',parent=None,lineNumber=0,**kwargs):
		self.name = name
		self.definitionString = definitionString
		self.source = source
		self.fullSource = fullSource or source
		self.parent = parent
		self.lineNumber = lineNumber

		self.nodes = []
		self.subgroups = []

		self.newObjectPattern = self.generateNewObjectPattern()
		self.newObjectAssignedPattern = self.generateNewObjectAssignedPattern()

		#TODO can we get rid of this?
		self.validObj = True

		#increment the identifier
		#Needed for the sake of a unique node name for graphviz
		global currentUID
		self.uid = currentUID
		currentUID += 1


	def __str__(self):
		'''
		__str__ is for printing to the DOT file
		'''
		#pdb.set_trace()
		ret = 'subgraph '+self.getUID()
		ret += '{\n'
		if self.nodes:
			for node in self.nodes:
				ret += node.getUID() + ' '
				#if node.isFileRoot:
				#	ret += ";{rank=source; %s}"%node.getUID()

			ret += ';\n'
		ret += 'label="%s";\n'%self.name;
		ret += 'style=filled;\n';
		ret += 'color=black;\n';
		ret += 'graph[style=dotted];\n'
		#pdb.set_trace()
		for subgroup in self.subgroups:
			ret += str(subgroup)
		ret += '}'
		return ret

	def getUID(self):
		try:
			if self.isAnon:
				return 'clusterANON'+str(self.uid)
			else:
				raise Exception()
		except:
			return 'cluster'+re.sub(r"[/\.\-\(\)\s]",'',self.name)+str(self.uid)

	def generateNodes(self):
		'''
		Find all function definitions, generate the nodes, and append them
		'''
		functionPatterns = self.generateFunctionPatterns()
		for pattern in functionPatterns:
			functionMatches = pattern.finditer(self.source.sourceString)
			for functionMatch in functionMatches:
				node = self.generateNode(functionMatch)
				self.nodes.append(node)

	def allNodes(self):
		'''
		Every node in this namespace and all descendent namespaces
		'''
		nodes = self.nodes
		for subgroup in self.subgroups:
			nodes += subgroup.allNodes()
		return nodes

	def getFileGroup(self):
		if self.parent:
			return self.parent.getFileGroup()
		else:
			return self

	def getFileName(self):
		return self.getFileGroup().name

	def getNamespace(self):
		'''
		called by children nodes to generate their namespaces
		'''
		#if parent:
		#TODO more complex namespaces involving parents
		return self.name

	def addNode(self,node):
		self.nodes.append(node)

	def generateNode(self,reMatch):
		'''
		Using the name match, generate the name, source, and parent of this node

		group(0) is the entire definition line ending at the new block delimiter like:
			def myFunction(a,b,c):
		group(1) is the identifier name like:
			myFunction
		'''
		name = reMatch.group(1)
		definitionString = reMatch.group(0)

		newBlockDelimPos = reMatch.end(0)
		beginIdentifierPos = reMatch.start(1)

		source = self.source.getSourceInBlock(newBlockDelimPos)
		fullSource = self.source.getSourceInBlock(newBlockDelimPos,fullSource=True)
		lineNumber = self.source.getLineNumber(beginIdentifierPos)
		return Node(name=name,definitionString=definitionString,source=source,fullSource=fullSource,parent=self,characterPos=beginIdentifierPos,lineNumber=lineNumber)


	def generateRootNodeName(self,name=''):
		if not name:
			name = self.name
		return "(%s %s frame (runs on import))"%(name,self.globalFrameName)


	def trimGroups(self):
		pass



class SourceCode(object):
	'''
	SourceCode is a representation of source text and a character to linenumber/file mapping
	The mapping must be kept consistent when SourceCode is sliced

	A sourcecode object is maintained internally in both Group and Node
	'''

	'''
	@abc.abstractproperty
	def blockComments(self):
		pass

	@abc.abstractproperty
	def inlineComments(self):
		pass
	'''
	#__metaclass__ = abc.ABCMeta

	#must be subclassed
	blockComments = []
	inlineComments = ''

	def __init__(self,sourceString,parentName='',characterToLineMap=None):
		'''
		Remove the comments and build the linenumber/file mapping while doing so
		'''
		self.sourceString = sourceString
		self.parentName = parentName

		if characterToLineMap:
			self.characterToLineMap = characterToLineMap
		else:
			self.characterToLineMap = {}

			self.removeCommentsAndStrings()

			if DEBUG:
				#print 'REMOVED COMMENTS',self
				with open('cleanedSource','w') as outfile:
					outfile.write(self.sourceString)

		#pprint.pprint(self.characterToLineMap)


	def __len__(self):
		return len(self.sourceString)

	def __getitem__(self,sl):
		'''
		If sliced, return a new object with the sourceString and the characterToLineMap sliced by [firstChar:lastChar]

		1. Slice the source string in the obvious way.
		2. Slice the charactertolinemap
			a. Remove character mappings that are not in between where we are shifting to
			b. Take remaining characterPositions and shift them over by start shift

		'''
		if type(sl) == int:
			return self.sourceString[sl]

		if type(sl) != slice:
			raise Exception("Slice was not passed")

		if sl.step and (sl.start or sl.stop):
			raise Exception("Sourcecode slicing does not support the step attribute (e.g. source[from:to:step] is not supported)")

		if sl.start is None:
			start = 0
		else:
			start = sl.start

		if sl.stop is None:
			stop = len(self.sourceString)
		elif sl.stop < 0:
			stop = len(self.sourceString)+sl.stop
		else:
			stop = sl.stop

		if start>stop:
			raise Exception("Begin slice cannot be greater than end slice. You passed SourceCode[%d:%d]"%(sl.start,sl.stop))

		ret = self.copy()

		ret.sourceString = ret.sourceString[start:stop]

		#filter out character mapping we won't be using
		shiftedCharacterToLineMap = {}
		characterPositions = ret.characterToLineMap.keys()
		characterPositions = filter(lambda p: p>=start and p<=stop,characterPositions)

		#shift existing character mappings to reflect the new start position
		#If we start with 0, no shifting will take place
		for characterPosition in characterPositions:
			shiftedCharacterToLineMap[characterPosition-start] = ret.characterToLineMap[characterPosition]

		#we need this to be sure that we can always get the line number no matter where we splice
		shiftedCharacterToLineMap[0] = self.getLineNumber(start)

		ret.characterToLineMap = shiftedCharacterToLineMap
		return ret

	def __add__(self,other):
		'''
		Add two pieces of sourcecode together shifting the character to line map appropriately
		'''

		#If one operand is nothing, just return the value of this operand
		if not other:
			return self.copy()

		if self.lastLineNumber()>other.firstLineNumber():
			raise Exception("When adding two pieces of sourcecode, the second piece must be completely after the first as far as line numbers go")

		sourceString = self.sourceString + other.sourceString

		shiftedCharacterToLineMap = {}
		characterPositions = other.characterToLineMap.keys()
		for characterPosition in characterPositions:
			shiftedCharacterToLineMap[characterPosition+len(self.sourceString)] = other.characterToLineMap[characterPosition]

		characterToLineMap = dict(self.characterToLineMap.items() + shiftedCharacterToLineMap.items())

		ret = SourceCode(sourceString=sourceString,characterToLineMap=characterToLineMap)

		return ret

	def __sub__(self,other):
		if not other:
			return self.copy()

		if self.firstLineNumber()>other.firstLineNumber() or self.lastLineNumber()<other.lastLineNumber():
			pdb.set_trace()
			raise Exception("When subtracting a piece of one bit of sourcecode from another, the second must lie completely within the first")

		firstPos = self.sourceString.find(other.sourceString)

		if firstPos == -1:
			pdb.set_trace()
			raise Exception('Could not subtract string starting with "%s" from source because string could not be found'%other.sourceString[:50].replace("\n","\\n"))

		lastPos = firstPos + len(other.sourceString)


		firstPart = self[:firstPos]

		secondPart = self[lastPos:]

		return firstPart+secondPart

	def copy(self):
		return copy.deepcopy(self)

	def getSourceInBlock(self,bracketPos):
		endBracketPos = self.endDelimPos(bracketPos)
		ret = self[bracketPos+1:endBracketPos]
		return ret

	def remove(self,stringToRemove):
		#if DEBUG:
		#	print 'Removing',stringToRemove

		firstPos = self.sourceString.find(stringToRemove)
		if firstPos == -1:
			pdb.set_trace()
			raise Exception("String not found in source")
		lastPos = firstPos + len(stringToRemove)

		#pdb.set_trace()
		return self[:firstPos]+self[lastPos:]



	def __nonzero__(self):
		'''
		__nonzero__ is object evaluates to True or False
		sourceString will be False when the sourceString has nothing or nothing but whitespace
		'''
		return self.sourceString.strip()!=''

	def firstLineNumber(self):
		try:
			return min(self.characterToLineMap.values())
		except ValueError:
			raise Exception("Sourcecode has no line numbers")

	def lastLineNumber(self):
		try:
			return max(self.characterToLineMap.values())
		except ValueError:
			raise Exception("Sourcecode has no line numbers")


	def pop(self):
		lastLinePos = self.sourceString.rfind('\n')
		ret = self.sourceString[lastLinePos:]
		self = self[:lastLinePos]

		return ret

	def getPosition(self,lineNumberRequest):
		'''
		Shortcut to get the position from the linenumber
		'''

		for pos,lineNumber in self.characterToLineMap.items():
			if lineNumber == lineNumberRequest:
				return pos

		raise Exception("Could not find line number in source")



	def getLineNumber(self,pos):
		'''
		Decrement until we find the first character of the line and can get the linenumber
		'''
		while True:
			try:
				return self.characterToLineMap[pos]
			except:
				pos-=1
				if pos < 0:
					raise Exception("could not get line number for position %d"%pos)

	def __str__(self):
		'''
		Mostly for debugging. Print the source with line numbers
		'''
		ret = ''
		for i, char in enumerate(self.sourceString):
			if i in self.characterToLineMap:
				ret += '%d: '%self.characterToLineMap[i]
			ret += char
		return ret

	def find(self,what,start=0):
		'''
		Pass through makes implementations cleaner
		'''
		return self.sourceString.find(what,start)

	def stringsToEmpty(self):
		'''
		i=0
		while i < len(fileAsString):
			if fileAsString[i]=='\\':
				i += 2
			elif singleQuote.match(fileAsString[i:]):
				try:
					i = re.search(r'[^\\]"',fileAsString[i:]).end(0)
				except Exception, e:
					print fileAsString[i:i+100]
					print e
			elif doubleQuote.match(fileAsString[i:]):
				i = re.search(r"[^\\]'",fileAsString[i:]).end(0)
			else:
				fStr += fileAsString[i]
				i+=1
		'''

	def extractBetweenDelimiters(self,delimiterA='{',delimiterB='}',startAt=0):
		'''
		Given a string and two delimiters, return the source between the first pair of delimiters after 'startAt'
		'''
		delimSize = len(delimiterA)
		if delimSize != len(delimiterB):
			raise Exception("delimiterA must be the same length as delimiterB")

		start = self.sourceString.find(delimiterA,startAt)
		if start == -1:
			return None
		start += delimSize

		endPos = endDelimPos(start,delimiterA,delimiterB)
		if endPos != -1:
			return self[start:endPos]
		else:
			return None

	def matchingBracketPos(self,bracketPos):
		delimiterA = self[bracketPos]
		if delimiterA == '{':
			delimiterB = '}'
		else:
			raise Exception('"%s" is not a known delimiter'%delimiterA)

		if self.sourceString[bracketPos+1]==delimiterB:
			return bracketPos + 1
		else:
			return self.endDelimPos(startAt=bracketPos+1,delimiterA=delimiterA,delimiterB=delimiterB)

	def endDelimPos(self,startAt,delimiterA='{',delimiterB='}'):
		delimSize = len(delimiterA)
		if delimSize != len(delimiterB):
			raise Exception("delimiterA must be the same length as delimiterB")

		count = 1
		i = startAt
		while i<len(self.sourceString) and count>0:
			tmp = self.sourceString[i:i+delimSize]
			if tmp==delimiterA:
				count += 1
				i+=delimSize
			elif tmp==delimiterB:
				count -= 1
				i+=delimSize
			else:
				i+=1

		if count == 0:
			return i-delimSize
		else:
			return -1

	def openDelimPos(self,pos):
		'''
		Go back to find the nearest open bracket without a corresponding close
		'''

		count = 0
		i = pos
		while i>=0 and count>=0:
			if self.sourceString[i] in ('}',')'):
				count += 1
			elif self.sourceString[i] in ('{','('):
				count -= 1
			i-=1

		if count==-1:
			return i+1
		else:
			return 0


	def removeCommentsAndStrings(self):
		'''
		Character by character, add those characters which are not part of comments to the return string
		Also generate an array of line number beginnings
		'''
		#if self.parentName:
		#	print "Removing comments and strings from %s..."%self.parentName
		#else:
		print "Removing comments and strings..."


		originalString = self.sourceString
		self.sourceString = ''
		self.characterToLineMap = {}
		lineCount = 1
		self.characterToLineMap[0] = lineCount #character 0 is line #1
		lineCount += 1 #set up for next line which will be two

		i=0

		inlineCommentLen = len(self.inlineComments)

		#begin analyzing charactes 1 by 1 until we reach the end of the originalString
		#-blockCommentLen so that we don't go out of bounds
		while i < len(originalString):
			#check if the next characters are a block comment
			#There are multiple types of block comments so we have to check them all
			for blockComment in self.blockComments:
				if type(blockComment['start']) == str:
					blockCommentLen = len(blockComment['start'])
					if originalString[i:][:blockCommentLen] == blockComment['start']:
						#if it was a block comment, jog forward
						prevI = i
						i = originalString.find(blockComment['end'],i+blockCommentLen)+blockCommentLen

						while originalString[i-1]=='\\':
							i = originalString.find(blockComment['end'],i+blockCommentLen)+blockCommentLen

						if i==-1+blockCommentLen:
							#if we can't find the blockcomment and have reached the end of the file
							#return the cleaned file
							return

						#increment the newlines
						lineCount+=originalString[prevI:i].count('\n')

						#still want to see the comments, just not what is inside
						self.sourceString += blockComment['start']+blockComment['end']

						break
				else:
					#is a regex blockcomment... sigh js sigh...
					match = blockComment['start'].match(originalString[i:])
					if match:
						#print match.group(0)
						#print originalString[i-5:i+5]
						prevI = i

						endMatch = blockComment['end'].search(originalString[i+match.end(0):])

						if endMatch:
							i = i+match.end(0)+endMatch.end(0)
						else:
							return

						#increment the newlines
						lineCount+=originalString[prevI:i].count('\n')
						break
			else:
				#check if the next characters are an inline comment
				if originalString[i:][:inlineCommentLen] == self.inlineComments:
					#if so, find the end of the line and jog forward. Add one to jog past the newline
					i = originalString.find("\n",i+inlineCommentLen+1)

					#if we didn't find the end of the line, that is the end of the file. Return
					if i==-1:
						return

					#lineCount += 1
				else:
					#Otherwise, it is not a comment. Add to returnstr
					self.sourceString += originalString[i]

					#if the originalString is a newline, then we must note this
					if originalString[i]=='\n':
						self.characterToLineMap[len(self.sourceString)] = lineCount
						lineCount += 1
					i+=1


class Mapper(object):
	'''
	The main class of the engine.
	Mappers are meant to be abstract and subclassed by various languages
	'''


	SINGLE_QUOTE_PATTERN = re.compile(r'(?<!\\)"')
	DOUBLE_QUOTE_PATTERN = re.compile(r"(?<!\\)'")

	files = {}

	def __init__(self,implementation,files):
		#importlib.import_module('languages.python','*')
		global Node,Edge,Group,Mapper,SourceCode
		Node = implementation.Node
		Edge = implementation.Edge
		Group = implementation.Group
		Mapper = implementation.Mapper
		SourceCode = implementation.SourceCode


		for f in files:
			with open(f) as fi:
				self.files[f] = fi.read()


	def map(self):
		'''
		I. For each file passed,
			1. Generate the sourcecode for that file
			2. Generate a group from that file's sourcecode
				a. The group init will recursively generate all of the subgroups and function nodes for that file
		II.  Trim the groups bascially removing those which have no function nodes
		III. Generate the edges
		IV.  Return the file groups, function nodes, and edges
		'''

		#get the filename and the fileString
		#only first file for now
		nodes = []
		fileGroups = []
		for filename,fileString in self.files.items():
			#remove .py from filename
			filename = self.cleanFilename(filename)
			print "Mapping %s"%filename

			#generate sourcecode (remove comments and add line numbers)
			source = SourceCode(fileString,parentName=filename)

			#Create all of the subgroups (classes) and nodes (functions) for this file
			print "Generating function nodes..."
			fileGroup = self.generateFileGroup(name=filename,source=source)
			fileGroups.append(fileGroup)

			#Append nodes generated to all nodes
			nodes += fileGroup.allNodes()

		#Trimming the groups mostly removes those groups with no function nodes
		for group in fileGroups:
			group.trimGroups()

		#Figure out what functions map to what
		print "Generating edges..."
		edges = generateEdges(nodes)

		#return everything we have done
		return fileGroups,nodes,edges

	def generateFileGroup(self,name,source):
		'''
		Dummy function probably superclassed
		'''
		return Group(name=name,source=source)

	def cleanFilename(self,filename):
		if '.' in filename:
			filename = filename[:filename.rfind('.')]

		#filename = filename.rsplit('/',1)[1]

		return filename

	def trimGroups(self):
		pass

	'''
	def generateNode(self,reMatch,fileStr,nodeType=None):
		if nodeType == 'anonymous':
			name = '(anonymous parameter)'
		else:
			if reMatch.group(1):
				group=1
			else:
				group=2
			name = reMatch.group(group)

		if DEBUG:
			print 'generateNode: %s'%name

		content = extractBetween(fileStr,'{','}',reMatch.end(0)-1) #-1 b/c we might be on the bracket otherwise
		lineNumber = self.getLineNumber(reMatch.end(0))
		return Node(name,content,lineNumber)
	'''





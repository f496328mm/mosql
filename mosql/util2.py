#!/usr/bin/env python
# -*- coding: utf-8 -*-

from functools import wraps
from datetime import datetime, date, time

def escape(s):
    return s.replace("'", "''")

def escape_identifier(s):
    return s.replace('"', '""')

class raw(str):

    def __repr__(self):
        return 'raw(%s)' % self

default = raw('DEFAULT')

def is_iterable_not_str(x):
    return not isinstance(x, basestring) and hasattr(x, '__iter__')

def qualifier(f):

    @wraps(f)
    def qualifier_wrapper(x):
        if isinstance(x, raw):
            return x
        elif is_iterable_not_str(x):
            return map(f, x)
        else:
            return f(x)

    return qualifier_wrapper

@qualifier
def value(x):

    if isinstance(x, (datetime, date, time)):
        x = str(x)

    if isinstance(x, basestring):
        return "'%s'" % escape(x)
    elif x is None:
        return 'NULL'
    elif isinstance(x, bool):
        # TODO: bit style
        return 'TRUE' if x else 'FALSE'
    else:
        return str(x)

@qualifier
def identifier(s):
    return s
    # TODO: switchable style
    return '"%s"' % escape_identifier(s)

@qualifier
def paren(s):
    return '(%s)' % s

def aggregater(f):

    @wraps(f)
    def aggregater_wrapper(x):
        if is_iterable_not_str(x):
            return f(x)
        else:
            return x

    return aggregater_wrapper

@aggregater
def concat_by_and(i):
    return ' AND '.join(i)

@aggregater
def concat_by_or(i):
    return ' OR '.join(i)

@aggregater
def concat_by_space(i):
    return ' '.join(i)

@aggregater
def concat_by_comma(i):
    return ', '.join(i)

allowed_operators = set([
    '<', '>', '<=', '>=', '=', '<>', '!=',
    'IS', 'IS NOT',
    'IN', 'NOT IN',
    'LIKE', 'NOTE LIKE',
    'NOT SIMILAR TO', 'SIMILAR TO',
    '~', '~*', '!~', '!~*',
])

def is_allowed_operator(op):
    return op.upper() in allowed_operators

def to_pairs(x):

    if hasattr(x, 'iteritems'):
        x = x.iteritems()
    elif hasattr(x, 'items'):
        x = x.items()

    return x

@aggregater
def build_where(x):

    ps = to_pairs(x)

    pieces = []

    for k, v in ps:

        # split the op out
        op = None
        if not isinstance(k, raw):
            space_pos = k.find(' ')
            if space_pos != -1:
                k, op = k[:space_pos], k[space_pos+1:]

        # qualify the k, op and v

        k = identifier(k)

        if op:
            op = op.upper()
            if not is_allowed_operator(op):
                op = None

        if not op:
            if is_iterable_not_str(v):
                op = 'IN'
            elif v is None:
                op = 'IS'
            else:
                op = '='

        v = value(v)
        if is_iterable_not_str(v):
            v = paren(concat_by_comma(v))

        pieces.append('%s %s %s' % (k, op, v))

    return concat_by_and(pieces)

@aggregater
def build_set(x):

    ps = to_pairs(x)

    pieces = []
    for k, v in ps:
        pieces.append('%s=%s' % (identifier(k), value(v)))

    return concat_by_comma(pieces)

# NOTE: To keep simple, the below classes shouldn't rely on the below functions

class Clause(object):

    def __init__(self, prefix, formatters):
        self.prefix = prefix
        self.formatters = formatters

    def format(self, x):
        for formatter in self.formatters:
            x = formatter(x)
        return '%s %s' % (self.prefix.upper(), x)

    def __repr__(self):
        return 'Clause(%s, %s)' % (self.prefix, self.formatters)

class Statement(object):

    def __init__(self, clauses):
        self.clauses = clauses

    def format(self, clause_args):

        for k in clause_args:
            new_k = k.replace('_', ' ')
            if new_k != k:
                clause_args[new_k] = clause_args[k]
                del clause_args[k]

        pieces = []
        for clause in self.clauses:
            arg = clause_args.get(clause.prefix)
            if arg is not None:
                pieces.append(clause.format(arg))
        return ' '.join(pieces)

    def __repr__(self):
        return 'Statement(%s)' % self.clauses

if __name__ == '__main__':

    # insert

    single_identifier = (identifier, )
    identifier_list = (identifier, concat_by_comma)

    insert_into = Clause('insert into', single_identifier)
    columns     = Clause('', (identifier, concat_by_comma, paren))
    values      = Clause('', (value, concat_by_comma, paren))
    returning   = Clause('returning', identifier_list)

    insert_into_stat = Statement([insert_into, columns, values, returning])

    # select

    single_value = (value, )
    where_list  = (build_where, )
    statement_list  = (concat_by_space, )

    select   = Clause('select'  , identifier_list)
    from_    = Clause('from'    , identifier_list)
    joins    = Clause(''        , statement_list)
    where    = Clause('where'   , where_list)
    group_by = Clause('group by', identifier_list)
    having   = Clause('having'  , where_list)
    order_by = Clause('order by', identifier_list)
    limit    = Clause('limit'   , single_value)
    offset   = Clause('offset'  , single_value)

    select_stat = Statement([select, from_, joins, where, group_by, having, order_by, limit, offset])

    # TODO: update
    # TODO: delete from
    # TODO: join, or_

    # tests

    print select_stat.format({'select': raw('*'), 'from': 'person', 'where': {'person_id like': 'me'}})
    print select_stat.format({'select': raw('*'), 'from': 'person', 'where': {'name': None}})
    print select_stat.format({'select': raw('*'), 'from': 'person', 'where': {'person_id not in': ['andy', 'bob']}})
    print select_stat.format({'select': raw('*'), 'from': 'person', 'where': (('person_id', 'mosky'), ('name', 'Mosky Liu'))})
    print select_stat.format({'select': raw('*'), 'from': 'person', 'where': 'person_id = any (select person_id from person)'})

    #def select(table, where=None, select=raw('*'), **clause_args):

    #    clause_args['from'] = table
    #    clause_args['where'] = where
    #    clause_args['select'] = select

    #    return select_stat.format(clause_args)

    #from timeit import timeit

    #print timeit(lambda: select('person', {'name': 'Mosky Liu'}, ('person_id', 'name'), limit=10, order_by='person_id'))
    # -> 40.8449561596

    #from mosql.common import select as old_select

    #print timeit(lambda: old_select('person', {'name': 'Mosky Liu'}, ('person_id', 'name'), limit=10, order_by='person_id'))
    # -> 67.9556078911

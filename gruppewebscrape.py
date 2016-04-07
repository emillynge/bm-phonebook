"""
Created on Wed Feb  3 19:51:34 2016

@author: emil
"""
from getpass import getpass
import requests
from bs4 import BeautifulSoup

html_doc = """<html>..."""

s = requests.session()

import re
from collections import defaultdict

def updateinfo(inf, resp):
    not_digit = re.compile('[^\d]+')
    mno_re = re.compile('mno=(\d+)')
    mail_re_dk = re.compile('[\w\._-]+@[\w\._-]+\.dk')
    mail_re_com = re.compile('[\w\._-]+@[\w\._-]+\.com')
    soup = BeautifulSoup(resp.content,'html.parser')
    headers = list()

    for row in soup.find_all('tr'):
        _headers = row.find_all('th')
        if _headers:
            headers = [header.text.strip() for header in _headers]
            continue
        person = dict()
        for cell, header in zip(row.find_all('td'), headers):
            if header == 'Navn':
                mno = mno_re.findall(cell.find_next('a').get('href'))
                person['mno'] = mno[0]
            person[header] = cell.text.strip()

        # mobile parser
        mob = not_digit.sub('', person['Mobil'])
        if len(mob) == 8:
            mob = '+45' + mob
        else:
            mob = '+' + mob
        person['mobile'] = mob

        # emails
        if 'Pårørende' in person:
            mails=set()
            mails.update(mail_re_dk.findall(person['Pårørende']))
            mails.update(mail_re_com.findall(person['Pårørende']))
            mails.update(mail_re_com.findall(person['Email']))
            mails.update(mail_re_dk.findall(person['Email']))
            person['mails'] = list(mails)
        inf[person['mno']].update(person)


def get_info(url):
    info = defaultdict(dict)
    r = s.get(url)
    updateinfo(info, r)
    r = s.get(url + '?view=extended', data={'view': 'extended'})
    updateinfo(info, r)
    return info


def get_mno_from_info(pers, info):
    for _pers in info.values():
        if _pers['Navn'].lower() == pers['Navn'].lower():
            return _pers['mno']


def get_participants(node, info=None):
    inf = defaultdict(dict)
    if node.isdigit():
        url = 'http://b21b.dk/node/{}/participant_list'.format(node)
    else:
        url = 'http://b21b.dk/{}/participant_list'.format(node)
    r = s.get(url)
    soup = BeautifulSoup(r.content,'html.parser')
    headers = list()

    for row in soup.find_all('tr'):
        _headers = row.find_all('th')
        if _headers:
            headers = [header.text.strip() for header in _headers]
            continue
        person = dict()
        for cell, header in zip(row.find_all('td'), headers):
            if header == 'Medlemsnummer':
                person['mno'] = cell.text.strip('Ret ')
            person[header] = cell.text.strip()

        if not person['mno'] and info:
            person['mno'] = get_mno_from_info(person, info)
        inf[person['mno']].update(person)
    return inf


def get_cancellations(node, info=None):
    if node.isdigit():
        url = 'http://b21b.dk/node/{}'.format(node)
    else:
        url = 'http://b21b.dk/{}'.format(node)
    r = s.get(url)
    soup = BeautifulSoup(r.content,'html.parser')
    for d in soup.find_all('div'):
        klass = d.get('class')
        if klass and 'dds-cancellation' in klass and 'group-cancellation' not in klass:
            break

    inf = dict()
    for row in d.find_all('tr'):
        _headers = row.find_all('th')
        if _headers:
            headers = [header.text.strip() for header in _headers]
            continue
        person = dict()
        for cell, header in zip(row.find_all('td'), headers):
            if header == 'Medlemsnummer':
                person['mno'] = cell.text.strip('Ret \n')
            person[header] = cell.text.strip()
        if not person['mno'] and info:
            person['mno'] = get_mno_from_info(person, info)
        inf[person['mno']] = person
    return inf


def get_no_respond(info, part, cancel, leaders=False, verbose=False):
    not_digit = re.compile('[^\d]')
    no_part = dict()
    for mno, person in info.items():
        if 'Patrulje' not in person:
            continue
        if mno not in part and mno in cancel:
            mob = not_digit.sub('', info[mno]['Mobil'])
            if len(mob) == 8:
                mob = '+45' + mob
            else:
                mob = '+' + mob
            no_part[mno] = {'mobile': mob, 'name': info[mno]['Navn'],
            'mail':info[mno]['Email'], 'mails':info[mno]['mails']}
            if verbose:
                no_part[mno].update(person)
    return no_part


class LoginFailed(IOError):
    pass

def check_login(resp):
    soup = BeautifulSoup(resp.content, 'html.parser')
    tag = soup.find('div', {'id': 'flashMessage'})
    if tag:
        return tag.text

def login(url, mno, pas):
    login_url = re.findall('https?://.*?\.dk/', url)
    if not login_url:
        raise LoginFailed('Url not valid. Should match https://awebsite.dk')
    login_url = login_url[0]

    r = s.get(login_url + 'dds/tologin')
    r = s.post('https://login.dds.dk/login/user/login',
               data={'data[user]': mno,
                     'data[password]': str(pas)})
    msg = check_login(r)

    if msg:
       raise LoginFailed(msg)


if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser('Reminders')
    parser.add_argument('enhed', type=str, nargs=1)
    parser.add_argument('node', type=str, nargs=1)
    parser.add_argument('-m', '--medlemsnummer', type=str, default=None, nargs=1,
                        dest='mno')
    parser.add_argument('-p', '--password', type=str, default=None, nargs=1,
                        dest='passw')

    args = parser.parse_args()
    node = args.node[0]
    enhed = args.enhed[0]

    login(args.mno, args.passw)
    part = get_participants(node)
    cancel = get_cancellations(node)
    info = get_info(enhed)


    np = get_no_respond(info, part, cancel)
    print(','.join(p['mobile'] for p in np.values()))
    print(','.join(','.join(p['mails']) for p in np.values()))
    #print(','.join(p['mobile'] for p in np.values()))
    #pprint(get_no_part())


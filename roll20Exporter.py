# -*- coding: utf-8 -*-
"""
Created on Thu Jun 11 13:06:27 2029

@author: JoergRue

Class to handle export to roll20 json
"""
from Wolke import Wolke
import Definitionen
import Objekte
import Talentbox
import os
import math
from collections import namedtuple
import logging
from Charakter import KampfstilMod
from Hilfsmethoden import Hilfsmethoden, WaffeneigenschaftException
import sys
import json
import time
import random


class roll20Exporter(object):
    """exports character data into a Json file for a roll20 character sheet"""

    def __init__(self):
        pass

    def exportCharacter(self, filename):
        Wolke.Char.aktualisieren()

        # load the file into memory
        with open(filename, "r", encoding="utf8") as read_file:
            data = json.load(read_file)

        # update data
        self.updateCharacterData(data["attribs"], Wolke.Char)

        # write back the data into the file
        with open(filename, "w", encoding="utf8") as write_file:
            json.dump(data, write_file, indent=4, ensure_ascii = False)

    def updateCharacterData(self, attribs, char):
        self.updateAttributes(attribs, char)
        self.updateGlobalValues(attribs, char)
        self.updateFertigkeiten(attribs, char)
        self.updateUebernatuerliches(attribs, char)
        self.updateWaffen(attribs, char)
        self.updateRuestung(attribs, char)

    def updateAttributes(self, attribs, char):
        for key in Definitionen.Attribute:
            self.setCurrentAttrValue(attribs, key.lower(), char.attribute[key].wert)

    def updateGlobalValues(self, attribs, char):
        self.setCurrentAttrValue(attribs, "wsb", char.ws)
        self.setCurrentAttrValue(attribs, "wsg", char.wsStern)
        self.setCurrentAttrValue(attribs, "mr", char.mr)
        self.setCurrentAttrValue(attribs, "behinderung", char.be)
        self.setCurrentAttrValue(attribs, "geschwindigkeit", char.gs)
        self.setCurrentAttrValue(attribs, "kampfreflexe", 4 if "Kampfreflexe" in char.vorteile else 0)
        isZauberer = char.aspBasis + char.aspMod > 0
        isGeweiht = char.kapBasis + char.kapMod > 0
        if isZauberer:
            self.setMaxAttrValue(attribs, "energy", char.asp.wert + char.aspBasis + char.aspMod)
        elif isGeweiht:
            self.setMaxAttrValue(attribs, "energy", char.kap.wert + char.kapBasis + char.kapMod)
        self.setMaxAttrValue(attribs, "schip", char.schipsMax)


    def updateFertigkeit(self, attribs, attrName, fert, char):
        self.setCurrentAttrValue(attribs, attrName, fert.wert)
        # Talente
        talStr = ""
        talente = sorted(fert.gekaufteTalente)
        for el2 in talente:
            if (len(talStr) > 0):
                talStr += ", "
            # code taken from pdfMeister, purpose not clear
            if el2.startswith("Gebräuche: "):
                talStr += el2[11:]
            elif el2.startswith("Mythen: "):
                talStr += el2[8:]
            elif el2.startswith("Überleben: "):
                talStr += el2[11:]
            else:
                talStr += el2
            if el2 in char.talenteVariable:
                vk = char.talenteVariable[el2]
                talStr += " (" + vk.kommentar + ")"
        self.setCurrentAttrValue(attribs, attrName + "_t", talStr)

    def updateFertigkeiten(self, attribs, char):
        attrNames = {
            "Athletik": "ath",
            "Heimlichkeit": "hei",
            "Mythenkunde": "myt",
            "Überleben": "ube",
            "Alchemie": "alc",
            "Selbstbeherrschung": "sel",
            "Wahrnehmung": "wah",
            "Handwerk":  "han",
            "Heilkunde": "hku",
            "Verschlagenheit": "ver",
            "Beeinflussung":  "bee",
            "Gebräuche": "geb",
            "Autorität": "aut",
            "Derekunde": "der",
            "Magiekunde": "mag"}

        assert len(attrNames) == len(Definitionen.StandardFerts) - 6 # nicht Kampffertigkeiten
        for fert in attrNames.keys():
            assert fert in Definitionen.StandardFerts
        for fertKey, fert in char.fertigkeiten.items():
            if fert.name in attrNames:
                self.updateFertigkeit(attribs, attrNames[fert.name], fert, char)
            elif fert.name == "Gebräuche und Sitten": # special to replace Gebräuche
                self.updateFertigkeit(attribs, "geb", fert, char)

        # Freie Fertigkeiten
        ffertcount = 1
        for fert in char.freieFertigkeiten:
            if fert.wert < 1 or fert.wert > 3 or not fert.name:
                continue
            val = fert.name + " "
            for i in range(fert.wert):
                val += "I"
            self.setCurrentAttrValue(attribs, "ffert" + str(ffertcount), val)
            ffertcount += 1

    def updateUebernatuerliches(self, attribs, char):
        # code taken from pdfMeister, pdfSechsterBlock (pull out function?)
        # Get number of talents
        talsList = []
        for f in char.übernatürlicheFertigkeiten:
            if char.übernatürlicheFertigkeiten[f].wert > 0 or\
                    len(char.übernatürlicheFertigkeiten[f].
                        gekaufteTalente) > 0:
                talsList.extend(char.übernatürlicheFertigkeiten[f].
                                gekaufteTalente)
        talsList = set(talsList)

        fertsList = []
        for f in char.übernatürlicheFertigkeiten:
            if char.übernatürlicheFertigkeiten[f].wert <= 0 and\
                    len(char.übernatürlicheFertigkeiten[f].
                        gekaufteTalente) == 0:
                continue
            fertsList.append(f)
        fertsList.sort(key = lambda x: (Wolke.DB.übernatürlicheFertigkeiten[x].printclass, x))

        # find highest talent value, talent could be in serveral fertigkeiten
        talsValues = {}
        for tal in talsList:
            talsValues[tal] = 0
        for fert in fertsList:
            fe = char.übernatürlicheFertigkeiten[fert]
            val = fe.probenwertTalent
            for tal in fe.gekaufteTalente:
                if val > talsValues[tal]:
                    talsValues[tal] = val

        talCount = 1
        for tal, val in talsValues.items():
            self.setCurrentAttrValue(attribs, "sn" + str(talCount), val)
            mod = ""
            if tal in char.talenteVariable:
                vk = char.talenteVariable[tal]
                mod = " (" + vk.kommentar + ")"
            self.setCurrentAttrValue(attribs, "sn" + str(talCount) + "_t", tal + mod)
            talCount += 1

    def updateWaffen(self, attribs, char):
        weaponCount = 1
        nkWeaponCount = 1
        fkWeaponCount = 1
        for weapon in char.waffen:
            waffenwerte = char.waffenwerte[weaponCount - 1]
            if type(weapon) == Objekte.Fernkampfwaffe or (weapon.name in Wolke.DB.waffen and Wolke.DB.waffen[weapon.name].talent == 'Lanzenreiten'):
                base = "fkw" + str(fkWeaponCount)
                self.setCurrentAttrValue(attribs, base + "_dmd", weapon.W6)
                self.setCurrentAttrValue(attribs, base + "_dmn", weapon.plus)
                self.setCurrentAttrValue(attribs, base + "_at", waffenwerte.AT)
                self.setCurrentAttrValue(attribs, base + "_t", weapon.anzeigename)
                fkWeaponCount += 1
            else:
                base = "w" + str(nkWeaponCount)
                self.setCurrentAttrValue(attribs, base + "_dmd", weapon.W6)
                # character sheet expects tp including kampfstil, but excluding damage bonus from KK
                # weapon.plus is without both
                # waffenwerte.TPPlus is including kampfstil and including damage bonus
                self.setCurrentAttrValue(attribs, base + "_dmn", waffenwerte.TPPlus - char.schadensbonus)
                # character sheet expects at including kampfstil / be, waffenwerte.AT is correct
                self.setCurrentAttrValue(attribs, base + "_at", waffenwerte.AT)
                self.setCurrentAttrValue(attribs, base + "_vt", waffenwerte.VT)
                self.setCurrentAttrValue(attribs, base + "_t", weapon.anzeigename)
                kl = 1 if "Kopflastig" in weapon.eigenschaften else 0
                self.setCurrentAttrValue(attribs, "kl" + base, kl)
                nkWeaponCount += 1
            weaponCount += 1

    def updateRuestung(self, attribs, char):
        if len(char.rüstung) > 0:
            el = char.rüstung[0]
            for zone in range(1, 7):
                self.setCurrentAttrValue(attribs, "wsg" + str(zone), el.rs[zone-1] + char.rsmod + char.ws)

    def setCurrentAttrValue(self, attribs, name, value):
        for attr in attribs:
            if "name" in attr and attr["name"] == name:
                attr["current"] = str(value)
                break
        else:
            attr = { "name": name, "current": str(value), "max": "", "id": self.generateAttrId() }
            attribs.append(attr)

    def setMaxAttrValue(self, attribs, name, value):
        for attr in attribs:
            if "name" in attr and attr["name"] == name:
                attr["max"] = str(value)
                break
        else:
            attr = { "name": name, "current": str(value), "max": str(value), "id": self.generateAttrId() }
            attribs.append(attr)

    def generateAttrId(self):
        # see https://app.roll20.net/forum/permalink/4258551/
        millis = int(round(time.time() * 1000))
        id = ""
        base64string = "-0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz"
        for e in range(0, 8):
            id += base64string[millis %64]
            millis = math.floor(millis / 64)
        for f in range(0, 12):
            id += base64string[random.randrange(0, len(base64string))]
        return id
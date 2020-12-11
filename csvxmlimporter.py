import csv
import re
from io import StringIO
from pathlib import Path

import pandas as pd
from chardet import detect
from lxml import etree
from typing import Optional, Dict, List


class CsvXmlImporter:
    __filenames: List[str]
    __combinedcsvfile: str
    dfx: pd.DataFrame
    __pdreadcsvsettings: Optional[Dict]

    def __init__(
            self,
            filenames: str or list,
            **pdreadcsvsettings
    ):
        self.__pdreadcsvsettings = pdreadcsvsettings

        # check if handed files are correct
        if type(filenames) == str:
            self.__filenames = [filenames]
        else:
            self.__filenames = filenames
        self.__validate_filenames()

        if self.__filenames[0].endswith((".xml", ".xsl")):
            self.__read_xmltocsv()
        elif self.__filenames[0].endswith(".csv"):
            self.__read_csv()

        # self.guess_settings()
        self.__call_pdloadcsv()

    def __validate_filenames(self):
        if self.__filenames[0].endswith(".csv"):
            for f in self.__filenames:
                if not f.endswith(".csv"):
                    raise ValueError(f"Invalid filenames extension: {f} should be .csv")

        elif self.__filenames[0].endswith((".xml", ".xsl")):
            xslfound = False
            for f in self.__filenames:
                if not f.endswith((".xml", ".xsl")):
                    raise ValueError(f"Invalid filenames extension: {f} should be .xml or .xsl")
                if f.endswith(".xsl"):
                    if xslfound:
                        raise ValueError(f"Multiple .xsl files passed")
                    else:
                        xslfound = True
            if not xslfound:
                raise ValueError(f"No .xsl filenames for parsing .xml to .csv passed")

        for f in self.__filenames:
            if not Path(f).exists():
                raise FileNotFoundError(f"File: {f} not found")

    def __call_pdloadcsv(self):
        self.dfx = pd.read_csv(
            StringIO(self.__combinedcsvfile),
            **self.__pdreadcsvsettings
        )

    def __read_csv(self):
        csvfiles = []
        for fn in self.__filenames:
            enc = detect(Path(fn).read_bytes())["encoding"]
            f = Path(fn).read_text(encoding=enc)
            csvfiles.append(f)
        self.__merge_csvfiles(*csvfiles)

    def __read_xmltocsv(self, **xslparam):
        xslfilename = [x for x in self.__filenames if x.endswith(".xsl")][0]
        self.__filenames.remove(xslfilename)
        transformer = etree.XSLT(etree.parse(xslfilename))
        csvfiles = []
        for fn in self.__filenames:
            csvfiles.append(str(transformer(etree.parse(fn), **xslparam)))
        self.__merge_csvfiles(*csvfiles)

    def __merge_csvfiles(self, *files: str):
        self.__combinedcsvfile = files[0]
        filesettings = self.__ascertain_settings(self.__combinedcsvfile)
        for f in files[1:]:
            if filesettings["names"] != self.__ascertain_settings(f)["names"]:
                raise ValueError("Files could not be merged")
            self.__combinedcsvfile += f'{filesettings["dialect"].lineterminator}{f}'
        self.__pdreadcsvsettings.update(filesettings)  # TODO move this elsewhere maybe

    def __ascertain_settings(self, file):
        """Ascertain settings by checking file content"""
        settings = {}
        with StringIO(file) as f:
            sample = f.readline()
            startsecondline = f.tell()
            sample += f.readline()

            dialect = csv.Sniffer().sniff(sample)
            if csv.Sniffer().has_header(sample):
                f.seek(startsecondline)
            else:
                f.seek(0)
                settings.update(header=None)

            firstline = next(csv.reader(f, dialect=dialect))
            headernames = []
            for i, item in enumerate(firstline):
                headernames.append(f'{i}_{self.__check_type(item)}')
            settings.update(
                dialect=dialect,
                names=headernames,
            )

        return settings

    @staticmethod
    def __check_type(string):
        types = {
            "Coordinate": re.compile(
                "^(N|S)?0*\d{1,2}°0*\d{1,2}(′|')0*\d{1,2}\.\d*(″|\")(?(1)|(N|S)) (E|W)?0*\d{1,2}°0*\d{1,2}(′|')0*\d{1,2}\.\d*(″|\")(?(5)|(E|W))$"
            ),
            "Email": re.compile(
                "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
            ),
            "Web-URL": re.compile(
                "^((ftp|http|https):\/\/)?(www.)?(?!.*(ftp|http|https|www.))[a-zA-Z0-9_-]+(\.[a-zA-Z]+)+((\/)[\w#]+)*(\/\w+\?[a-zA-Z0-9_]+=\w+(&[a-zA-Z0-9_]+=\w+)*)?$"
            ),
            "Time": re.compile(
                "^[0-2]\d:[0-6]\d:[0-6]\d$"
            ),
            "Date": re.compile(
                "^[0-3]?[0-9][/.][0-3]?[0-9][/.](?:[0-9]{2})?[0-9]{2}$"
            )
        }
        for key in types:
            if types[key].match(string):
                return key
        return "String"

    def set_settings(self, **kwargs):
        changedsettings = dict(kwargs.items() - self.__pdreadcsvsettings.items())

        if changedsettings:
            self.__pdreadcsvsettings.update(changedsettings)
            self.__call_pdloadcsv()

    def guess_settings(self):
        """guess settings after seeing csv filenames for first time"""
        # FIXME fix sniffer
        # enc = detect(Path(self.__filenames).read_bytes())
        # with open(self.__filenames, mode="r", encoding=enc["encoding"]) as f:
        #     # read first few lines as samples
        #     sample = ""
        #     for _ in range(3):
        #         sample += f.readline()
        #
        #     # sniff the sample
        #     # FIXME set options for header properly
        #     # self.__pdreadcsvsettings["headlinepresent"] = csv.Sniffer().has_header(sample)
        #     dialect = csv.Sniffer().sniff(sample)
        #
        # # TODO guess dtpye
        # # TODO read header names if headline is present
        #
        # self.__pdreadcsvsettings.update(
        #     encoding=enc["encoding"],
        #     sep=dialect.delimiter,
        #     skipinitialspace=dialect.skipinitialspace,
        #     quotechar=dialect.quotechar,
        #     doublequote=dialect.doublequote,
        #     quoting=dialect.quoting,
        #     escapechar=dialect.escapechar,
        #     # lineterminator=dialect.lineterminator
        # )

        # if not specified by the user use common german/engl true false values
        if "true_values" not in self.__pdreadcsvsettings:
            self.__pdreadcsvsettings["true_values"] = ["WAHR", "wahr", "Wahr", "true", "True", "TRUE", "doch"]
        if "false_values" not in self.__pdreadcsvsettings:
            self.__pdreadcsvsettings["false_values"] = ["FALSCH", "falsch", "Falsch", "false", "False", "FALSE", "nein"]

    def return_dict(self):
        return self.dfx.to_dict()
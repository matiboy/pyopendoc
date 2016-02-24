import re

from .opendocument import OpenDocument, NAMESPACES

class OpenSpreadsheetDocument(OpenDocument):

    REPEAT_ROWS_STR = "{%s}number-rows-repeated" % NAMESPACES["table"]
    REPEAT_COLS_STR = "{%s}number-columns-repeated" % NAMESPACES["table"]

    ROW_TAG = "{%s}table-row" % NAMESPACES["table"]
    COL_TAG = "{%s}table-cell" % NAMESPACES["table"]
    TXT_TAG = "{%s}p" % NAMESPACES["text"]

    def __init__(self, filepath=None):
        super(OpenSpreadsheetDocument, self).__init__(filepath)
        self._open_sheets = {}

    def _get_sheet(self, sheet_no, xmlf=None):
        xml_file = xmlf if xmlf else self.get_file(self.CONTENT_FILE)
        sheets = xml_file.root.findall(".//table:table", NAMESPACES)
        try:
            sheet = sheets[sheet_no]
        except KeyError:
            sheet = sheets[0]
        return sheet

    def _get_colrow_from_address(self, address="A1"):
        offset = 64
        addr = address.upper()
        base = (ord('Z') - offset)

        column_rep = re.sub("\d", "", addr)
        row_rep = re.sub("\D", "", addr)

        column_letter_value = [ord(c) - offset for c in column_rep]
        column = 0
        cl_count = len(column_letter_value)
        for i in range(0, cl_count):
            r_index = cl_count - (i + 1)
            value = column_letter_value[r_index]
            column += (value * (base ** i))
        column -= 1

        row = int(row_rep) - 1

        return (column, row)

    def _get_address_from_colrow(self, column=0, row=0):
        import math

        offset = 64
        base = (ord('Z') - offset)

        colval = column + 1
        values = []
        times_into = 1
        divisor = 1
        while times_into:
            times_into = math.floor(colval/divisor)
            if times_into:
                divisor *= base
            else:
                divisor /= base

        while divisor > 1:
            times_into = math.floor(colval/divisor)
            colval -= divisor
            values.append(times_into)
            divisor /= base
        times_into = math.floor(colval/divisor)
        values.append(times_into)

        # propagate value decrement from back of list
        # e.g. [1, 1, 0] -> [26, 26]
        values_count = len(values)
        for i in range(0, values_count - 1):
            r_index = values_count - (i + 1)
            this_val = values[r_index]
            if this_val is 0:
                del values[r_index]
                for j in range(values_count - r_index, -1, -1):
                    values[j] -= 1
                    if values[j] is 0:
                        values[j] = base
                    else:
                        break
                break

        column_rep = "".join([chr(value + offset) for value in values])

        row_rep = str(row + 1)

        return "{}{}".format(column_rep, row_rep)

    def _seek_to_row(self, sheet_element, target_row, limit):
        rows = 0
        non_rows = 0

        rows_list = list(sheet_element)

        current_index = non_rows + rows
        while current_index < len(rows_list):
            current_index = non_rows + rows # use in operations on the sheet element, to skip over
                                            # elements that are not of interest to us
            target_index = non_rows + target_row
            row = rows_list[current_index]
            if row.tag != self.ROW_TAG:
                non_rows += 1
                continue

            # If we run into the limit row, prepend before it
            if bool(limit) and list(list(row)[0])[0].text.upper() == limit:
                attr = rows_list[current_index - 1].attrib
                sheet_element.insert(current_index, self.get_content_file().new_element(self.ROW_TAG, attr))
                rows_list = list(sheet_element)
                row = rows_list[current_index]

            # If we run into a row with the repeated rows attribute, and we need to dereference a row
            # within the repeat, partially expand it into real rows, at least up to the targetted row
            if self.REPEAT_ROWS_STR in row.attrib:
                skipped_rows = int(row.attrib[self.REPEAT_ROWS_STR])
                if current_index <= target_index < (current_index + skipped_rows):
                    # TODO: accomodate inserting cells that are skipped
                    attr = row.attrib.copy()
                    del attr[self.REPEAT_ROWS_STR]
                    to_be_created = target_index - current_index
                    for i in range(0, to_be_created):
                        new_row = self.get_content_file().new_element(self.ROW_TAG, attr)
                        row_cells = list(row)
                        for i in range(0, len(row_cells)):
                            cell_attr = row_cells[i].attrib.copy()
                            new_cell = self.get_content_file().new_element(self.COL_TAG, cell_attr)
                            new_row.insert(i, )
                        sheet_element.insert(current_index + i, new_row)

                    if to_be_created is skipped_rows:
                        sheet_element.remove(row)
                    elif skipped_rows - to_be_created == 1:
                        del row.attrib[self.REPEAT_ROWS_STR]
                    elif skipped_rows - to_be_created > 1:
                        row.attrib[self.REPEAT_ROWS_STR] = str(skipped_rows - to_be_created)

                    rows_list = list(sheet_element)
                    #row = rows_list[current_index]
                    return rows_list[target_index]
                elif rows < target_row: # skip over repeated rows if target row lies beyond them
                    rows += skipped_rows
                    continue

            if rows < target_row:
                rows += 1
                continue

            return row

        raise IndexError

    def _seek_to_column(self, row_element, target_column):
        columns = 0
        cells_list = list(row_element)

        if not cells_list:
            attr = {}
            new_cell = self.get_content_file().new_element(self.COL_TAG, attr)
            new_cell.append(self.get_content_file().new_element(self.TXT_TAG))
            list(new_cell)[0].text = "0"
            row_element.insert(0, new_cell)
            cells_list = list(row_element)

        while columns < len(cells_list):
            cell = cells_list[columns]
            if self.REPEAT_COLS_STR in cell.attrib:
                to_be_created = int(cell.attrib[self.REPEAT_COLS_STR])
                attr = cell.attrib.copy()
                del attr[self.REPEAT_COLS_STR]
                for i in range(0, to_be_created):
                    new_cell = self.get_content_file().new_element(self.COL_TAG, attr)
                    new_cell.append(self.get_content_file().new_element(self.TXT_TAG))
                    list(new_cell)[0].text = "0"
                    row_element.insert(columns + i, new_cell)
                row_element.remove(cell)
                cells_list = list(row_element)
                cell = cells_list[columns]

            if columns is target_column:
                return cell
            columns += 1

        while columns <= target_column:
            attr = cell.attrib.copy()
            new_cell = self.get_content_file().new_element(self.COL_TAG, attr)
            new_cell.append(self.get_content_file().new_element(self.TXT_TAG))
            list(new_cell)[0].text = "0"
            row_element.insert(columns, new_cell)
            cells_list = list(row_element)
            cell = cells_list[columns]
            if columns is target_column:
                return cell
            columns += 1

        raise IndexError # lets fail here, since the row code section is supposed to traverse straight
                         # towards the correct row

    def _get_cell_from_colrow(self, target_column, target_row, sheet_no=0, xmlf=None, limit="TOTAL"):
        sheet = self._get_sheet(sheet_no, xmlf)

        row = self._seek_to_row(sheet, target_row, limit)
        return self._seek_to_column(row, target_column)


    def set_cell(self, address, value=""):
        cell = self._get_cell_from_colrow(*self._get_colrow_from_address(address))
        cell.set("{%s}value" % NAMESPACES["office"], str(value))
        list(cell)[0].text = str(value)

    def set_range(self, startaddress, values=[[]]):
        initial_column, initial_row = self._get_colrow_from_address(startaddress)
        row_offset = 0
        for row in values:
            row_no = initial_row + row_offset
            col_offset = 0
            for value in row:
                col_no = initial_column + col_offset
                cell = self._get_cell_from_colrow(col_no, row_no)
                cell.set("{%s}value" % NAMESPACES["office"], str(value))
                list(cell)[0].text = str(value)
                col_offset += 1
            row_offset += 1


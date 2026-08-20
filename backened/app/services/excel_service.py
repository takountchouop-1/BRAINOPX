import openpyxl
from fastapi import HTTPException, status


def extract_column_headers(file_path: str) -> list[str]:
    """
    Opens an Excel file and reads the header row (first row) of the first
    sheet, returning a clean list of column names.
    """
    try:
        workbook = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not read the Excel file. Make sure it's a valid .xlsx file. ({e})",
        )

    sheet = workbook.active
    first_row = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), None)
    workbook.close()

    if not first_row:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file appears to be empty.",
        )

    headers = [str(cell).strip() for cell in first_row if cell is not None and str(cell).strip()]

    if not headers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No column headers were found in the first row of the file.",
        )

    return headers


def read_data_rows(file_path: str) -> list[dict]:
    """
    Reads every data row (everything after the header row) from an Excel
    file and returns it as a list of dicts: [{"Column Name": value, ...}, ...]
    Row numbers are 1-based and refer to the actual Excel row (so row 2 is
    the first data row, since row 1 is the header) — this makes error
    messages like "row 5" line up with what the user sees when they open
    the file themselves.
    """
    try:
        workbook = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not read the Excel file. ({e})",
        )

    sheet = workbook.active
    rows_iter = sheet.iter_rows(values_only=True)

    header_row = next(rows_iter, None)
    if not header_row:
        workbook.close()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file appears to be empty.")

    headers = [str(cell).strip() if cell is not None else "" for cell in header_row]

    data_rows = []
    for row_index, row_values in enumerate(rows_iter, start=2):  # start=2: Excel row numbering after header
        # Skip fully blank rows
        if all(v is None or str(v).strip() == "" for v in row_values):
            continue

        row_dict = {"_row_number": row_index}
        for col_name, value in zip(headers, row_values):
            if col_name:
                row_dict[col_name] = value
        data_rows.append(row_dict)

    workbook.close()
    return data_rows
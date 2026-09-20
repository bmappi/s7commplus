@real_plc
Feature: Read a known non-optimized data block over S7CommPlus

  @smoke
  Scenario: Read the canonical fixture
    Given the client uses the configured S7CommPlus security mode
    And the non-optimized read-only DB has the documented canonical layout
    When I read the complete fixture DB
    Then INT, REAL, BYTE, WORD, DWORD, DINT, CHAR and BOOL values match the fixture
    And individual reads return the same values as the complete-block read

  @smoke
  Scenario: Read multiple values in one request
    Given the client uses the configured S7CommPlus security mode
    And the non-optimized read-only DB has the documented canonical layout
    When I read values of different sizes in one multi-variable request
    Then every value matches the fixture

Feature: Stickfix logger configuration
  Scenario Outline: Configures handlers only once per logger context
    Given a logger context "<context>"
    When I instantiate the logger <count> times
    Then the logger has exactly 1 console handler
    And the logger has exactly 1 rotating file handler
    And the log file is created

    Examples:
      | context                 | count |
      | stickfix.logger.single  | 1     |
      | stickfix.logger.reused  | 3     |

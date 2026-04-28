# Changelog

## 2026.4.9

- Huge simplification of the charging during off-peak hours.

## 2026.4.8

- Add an explicit option for responsive batteries.

## 2026.4.7

- Add the ability to charge the battery during off-peak hours ;
- Refactor : more files, shorter.

## 2026.4.6

- Finer adjustments to be closer to 0 W and bug fixes.

## 2026.4.5

- Big simplification of the logic :
  - No more priority battery, the SOC is only used ;
  - The cooldown chooses the allocation : the slow batteries gets a conservative setpoint that won't move often, while the quick batteries fill the gaps.

## 2026.4.4

- Many bug fixes in the handling of batteries.

## 2026.4.3

- A battery that goes above 90 % is now considered a priority.

## 2026.4.2

- New strategy to minimise losses ;
- Adding some logs to check what happens.

## 2026.4.1

- Should export less energy.

## 2026.4

- Initial version.

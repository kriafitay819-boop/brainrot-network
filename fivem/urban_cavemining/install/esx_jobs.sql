-- urban_cavemining: miner job for es_extended (run once on your database, then restart)
INSERT IGNORE INTO `jobs` (`name`, `label`) VALUES ('miner', 'כורה');

INSERT IGNORE INTO `job_grades` (`job_name`, `grade`, `name`, `label`, `salary`, `skin_male`, `skin_female`) VALUES
    ('miner', 0, 'apprentice', 'כורה מתחיל', 60, '{}', '{}'),
    ('miner', 1, 'miner', 'כורה', 90, '{}', '{}'),
    ('miner', 2, 'senior', 'כורה בכיר', 120, '{}', '{}'),
    ('miner', 3, 'boss', 'מנהל המכרה', 160, '{}', '{}');

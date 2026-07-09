## had complexity in handling rolling statistics.
- we had decided to have upto 1hr of rolling statistics.
    - while doing the streaming pipeline - it came complex to maintain that 1hr worth of window statistics.
    - and most of the time this 1hr statistics features will be sparse.
    - so, had a feature analysis to see are those features actually helpful or not ?
    - **turned out the features are actually reducing the performance.**
    - removing that increase the f1-score from 61% to 72%
    - so removed those rolling statistic featues for simple handling of steaming data. - no look back needed.



## training - production data skweness
- the training data was having 3-7 logs per 30s. but the production was having ~150 logs per 30s.
- So all the logs became anomaly.
- why this is a big problem?
    - we have distance based features log_count, error_count, fatal_count, warn_count, info_count, debug_count
    - having distance based features is a wrong idea for DBSCAN - this happened because previously the choosesn model was isolation forest which is not affected by the scale of the features.
    - but still the log_count adds more value, sudden increase inthe log count is a strong sign of anomaly - so we will keep and remove the **feature drift**.
    - SOLUTION: Make the traing data to represent the production data.
    - we can say in production for now there will be 100 - 150 / 30sec messages.



## sythetic data generation - 
- not able to generate a good fit of sythetic data for 150 messages per 30 sec. 
- this is soo not good having no pattern.
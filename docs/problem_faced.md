## had complexity in handling rolling statistics.
- we had decided to have upto 1hr of rolling statistics.
    - while doing the streaming pipeline - it came complex to maintain that 1hr worth of window statistics.
    - and most of the time this 1hr statistics features will be sparse.
    - so, had a feature analysis to see are those features actually helpful or not ?
    - **turned out the features are actually reducing the performance.**
    - removing that increase the f1-score from 61% to 72%
    - so removed those rolling statistic featues for simple handling of steaming data. - no look back needed.


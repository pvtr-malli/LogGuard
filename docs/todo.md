- latency computation.
5️⃣ How you would measure “real-time” in your project

You should actually measure this:

Event time  → Kafka ingestion time
Kafka time → Dask processing start
Processing start → Alert emitted


Report:

p50 latency

p95 latency

This impresses interviewers.

The framwork will be:

Log Producers
     ↓
   Kafka
     ↓
Stream Processor (Dask)
     ↓
Anomaly Scoring
     ↓
Results Store
     ↓
Dashboard



- delete summary at notebooks end
- will do error analysis
- setup kafka and make some code to push data continuousely

- then we will do prediction pipeline
- itegrate to a dashboard for alerts 
- readme

- nice architecture diagram
- latency finding and throughtput finding code.




# interview points:
- “I generated historical log data with realistic distributions and injected rare anomalies to train and validate an unsupervised anomaly detection model offline before deploying it to a streaming pipeline.”
- the realistic patterns ingected are - sudden error spikes, cascade failures, new exception/error types.
- geenrated around 1l training data.
- we can add the frequnecy and error_rate features - easy to understand.
   - **Volume Features:**
   - `log_count`: Total logs per window.
   - `error_count`: ERROR logs per window.
   - `fatal_count`: FATAL logs per window.
   - `warn_count`: WARN logs per window.
   - `critical_count`: ERROR + FATAL combined.

   **Frequency Features (Rates):**
   - `error_rate`: error_count / log_count.
   - `fatal_rate`: fatal_count / log_count.
   - `warn_rate`: warn_count / log_count.
   - `critical_rate`: critical_count / log_count.
   - `warn_to_info_ratio`: warn_count / info_count.
- we can add time series based features - like 5 mins rolling avg for each 30 sec.
   - rolling max, rolling std, error_rate rolling p95, critical_rate_max 
   - basically we can add all the frequency and error_rate features - rolling min,max,std,p95.

- Parse logs into templates (not done can be done)
   - New template appeared
   - Rare template frequency spike
   - Known template disappeared

- “I intentionally avoided heavy BERT embeddings initially because log messages are semi-structured. TF-IDF and template-based clustering provide faster, more interpretable anomaly detection. BERT can be added later if semantic variation becomes a limitation.”
- and logs are pretty much repeatative - if we preprocess well we can make all the same logs fall into same cluster. - so keyword based works better .
- and this mehtod is faster comparitable than BERT embeddings or any embeddings.
- This does the job.

- went to single consumer - since the throughput is less aorund 10k messages/sec.

     - [ ] if consumer == partition: all read one one partition independatantly
     - [ ] if consumer(5) > partition(3): 2 sits ideal
     - [ ] if consumer(2) < partition(3): consumer 1 does more job 
     - [ ] when having mulitple consumers, need to make sure of the timestamp order to do the rolling features properly.
     - [ ] Here there is no need of it.
- understand how the volumn data is persisted on the disk
     - docker container write to the volumn directories -> not maintained by docker container file system so when container dies the data stays.
     - the written datas in the volumn right to the below places in the disk.
     - [ ] ## How Docker volumns actually stores it (OS level)
     
     ### On Linux
     `/var/lib/docker/volumes/your_volumn/_data/file_name,txt`
     ### On macOS / Windows
     
     - [ ] Stored inside Docker Desktop’s **Linux VM disk**
          
     - [ ] That disk is a large virtual file (e.g. `data.raw`)
          
     - [ ] Still real disk I/O, just virtualized
          
     - [ ] If you delete the container the data will be there - but if you delte the volumn the data is lost
     - if you want to avoid the disk failure - opt for clode volume storage, are replicate it.


- how can you reduce the latency more in big logs ? 
     - increase partition - make the feature extraction prallel (frequency and text extract can happen in prallel)
- to avoid data lose;
     - increase teh kafka worker to 3.
     - KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 3  # Currently 1!










# anomaly detection:
- there is 3 types of anomaly:
- If a single data instance displays unexpected behavior related to the rest of data, then that instance can be called a point anomaly.
- If a single data instance displays unexpected behavior related to some part of the surrounding data (context), then that instance can be called a contextual anomaly
- If a set of data instances displays unexpected behavior related to the rest of the data, then that set of instances can be called a collective anomaly

- in Anomaly detection can be 2 types - point anomaly(binary-classification) and collective anomaly (change-point detection method has to be followed for this)
- in log its basically **collective anomaly because just on log can't be a anomaly** - but in our case **we aggregated over 30s window** and finding a window is anomaly or not. Now this becomes a point anomaly case so we can use a binary classificaion/outlier detection/one-class classification for this case and use binary classification metrics itself.

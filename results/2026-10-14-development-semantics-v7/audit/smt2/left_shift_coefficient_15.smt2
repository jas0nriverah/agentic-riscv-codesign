(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x181 (bvmul x (_ bv32768 32))))
(let ((?x179 (bvshl x (_ bv15 32))))
(and (distinct ?x179 ?x181) true))))
(check-sat)

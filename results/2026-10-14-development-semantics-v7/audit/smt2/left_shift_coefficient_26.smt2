(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x279 (bvmul x (_ bv67108864 32))))
(let ((?x277 (bvshl x (_ bv26 32))))
(and (distinct ?x277 ?x279) true))))
(check-sat)

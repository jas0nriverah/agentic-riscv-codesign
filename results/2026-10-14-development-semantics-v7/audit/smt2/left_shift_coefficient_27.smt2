(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x288 (bvmul x (_ bv134217728 32))))
(let ((?x286 (bvshl x (_ bv27 32))))
(and (distinct ?x286 ?x288) true))))
(check-sat)

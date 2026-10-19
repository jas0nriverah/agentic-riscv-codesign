(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x75 (bvmul x (_ bv8 32))))
(let ((?x73 (bvshl x (_ bv3 32))))
(and (distinct ?x73 ?x75) true))))
(check-sat)

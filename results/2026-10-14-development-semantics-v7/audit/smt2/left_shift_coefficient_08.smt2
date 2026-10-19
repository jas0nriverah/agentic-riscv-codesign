(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x118 (bvmul x (_ bv256 32))))
(let ((?x116 (bvshl x (_ bv8 32))))
(and (distinct ?x116 ?x118) true))))
(check-sat)

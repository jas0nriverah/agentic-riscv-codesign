(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x41 (bvadd independent_opaque_1 (_ bv3 32))))
(let ((?x47 (bvshl independent_opaque_0 (bvand (_ bv8 32) (_ bv31 32)))))
(let ((?x446 (bvadd ?x47 ?x41)))
(let ((?x23 (bvadd ?x41 ?x47)))
(and (distinct ?x23 ?x446) true))))))
(check-sat)
